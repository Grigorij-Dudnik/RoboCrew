"""
hardware.py — SO-101 follower arm + scene/wrist USB cameras for MolmoAct2.

Extracted from molmo_so101 (setup/robot.py, setup/wrist_camera.py, setup/wrist_v4l2.py).

- FollowerArm wraps LeRobot's SOFollower; all serial I/O runs in a background
  thread. Callers use set_target() / get_state() without blocking. lerobot is
  imported lazily so importing this module stays torch/lerobot-free.
- OpenCVCapture: scene USB camera (background frame grabber).
- WristCamera: wrist USB camera with v4l2 manual white-balance + optional
  adaptive-brightness controller.
- warmup_cameras(): block until both cameras produce frames.
"""
import os
import subprocess
import threading
import time

import cv2
import numpy as np

from .frame_transforms import JOINT_COUNT

MOTOR_NAMES = [
    "shoulder_pan", "shoulder_lift", "elbow_flex",
    "wrist_flex", "wrist_roll", "gripper",
]
_MAX_JOINT_DELTA = 10.0  # degrees per worker iteration — inner rate limiter
_WORKER_PERIOD_S = 1.0 / 60.0


# ── v4l2 helpers ─────────────────────────────────────────────────────────────
def _v4l2_device(cam_id) -> str:
    """Resolve an int index or a /dev path to a v4l2 device path."""
    if isinstance(cam_id, str) and cam_id.startswith("/dev/"):
        return cam_id
    return f"/dev/video{cam_id}"


def set_v4l2(cam_id, **ctrls):
    """Quietly apply a batch of v4l2 controls. Silent no-op if v4l2-ctl is missing."""
    if not ctrls:
        return
    arg = ",".join(f"{k}={v}" for k, v in ctrls.items())
    try:
        subprocess.run(
            ["v4l2-ctl", "-d", _v4l2_device(cam_id), "-c", arg],
            check=False, capture_output=True,
        )
    except FileNotFoundError:
        pass


def reset_wrist_to_auto(cam_id):
    """Restore the wrist camera to auto AE / auto WB / brightness=0. Idempotent."""
    set_v4l2(cam_id, auto_exposure=3, white_balance_automatic=1, brightness=0)


# ── Follower arm ─────────────────────────────────────────────────────────────
class FollowerArm:
    """Drives the SO-101 follower arm via LeRobot's SOFollower driver.

    All serial I/O is handled by a single background worker thread that
    alternates write / read on the half-duplex Feetech bus. Call set_target()
    and get_state() from any thread; they touch only lock-protected slots.
    """

    def __init__(self, port: str = "/dev/ttyACM0", simulate: bool = False):
        self.simulate = simulate
        self._target = np.zeros(JOINT_COUNT, dtype=np.float32)
        self._state  = np.zeros(JOINT_COUNT, dtype=np.float32)
        self._target_lock  = threading.Lock()
        self._state_lock   = threading.Lock()
        self._torque_lock  = threading.Lock()
        self._torque_desired = True
        self._stop   = threading.Event()
        self._thread = None

        if not simulate:
            try:
                from lerobot.robots.so_follower import SOFollower
                from lerobot.robots.so_follower.config_so_follower import SOFollowerRobotConfig
                self.robot = SOFollower(SOFollowerRobotConfig(
                    port=port, id="so_follower", use_degrees=True
                ))
                self.robot.connect()
                print(f"[Follower] Connected on {port}")
                obs  = self.robot.get_observation()
                init = np.array([obs[f"{n}.pos"] for n in MOTOR_NAMES], dtype=np.float32)
                self._target = init.copy()
                self._state  = init.copy()
                self._thread = threading.Thread(target=self._worker_loop, daemon=True)
                self._thread.start()
            except Exception as e:
                print(f"[Follower] Could not connect: {e} — falling back to simulation")
                self.simulate = True
        else:
            print("[Follower] Simulation mode")

    def _worker_loop(self):
        torque_actual = False
        last_written  = self._target.copy()
        while not self._stop.is_set():
            with self._torque_lock:
                desired = self._torque_desired
            if desired != torque_actual:
                try:
                    if desired:
                        self.robot.bus.enable_torque()
                        print("[Follower] Torque enabled")
                    else:
                        self.robot.bus.disable_torque()
                        print("[Follower] Torque disabled")
                    torque_actual = desired
                except Exception as e:
                    print(f"[Follower] torque transition error: {e}")

            if torque_actual:
                with self._target_lock:
                    target = self._target.copy()
                delta = np.clip(target - last_written, -_MAX_JOINT_DELTA, _MAX_JOINT_DELTA)
                last_written = last_written + delta
                try:
                    action = {f"{n}.pos": float(last_written[i])
                              for i, n in enumerate(MOTOR_NAMES)}
                    self.robot.send_action(action)
                except Exception as e:
                    print(f"[Follower] send_action error: {e}")

            try:
                obs   = self.robot.get_observation()
                state = np.array([obs[f"{n}.pos"] for n in MOTOR_NAMES], dtype=np.float32)
                with self._state_lock:
                    self._state = state
            except Exception as e:
                print(f"[Follower] get_observation error: {e}")
            time.sleep(_WORKER_PERIOD_S)

    def set_target(self, target: np.ndarray):
        if self.simulate:
            with self._target_lock:
                delta = np.clip(target - self._target, -_MAX_JOINT_DELTA, _MAX_JOINT_DELTA)
                self._target = self._target + delta
            with self._state_lock:
                self._state = self._target.copy()
            return
        with self._target_lock:
            self._target = target.astype(np.float32, copy=True)

    def get_state(self) -> np.ndarray:
        with self._state_lock:
            return self._state.copy()

    def request_torque(self, on: bool):
        if self.simulate:
            return
        with self._torque_lock:
            self._torque_desired = on

    def disconnect(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if not self.simulate:
            try:
                self.robot.bus.disable_torque()
            except Exception:
                pass
            self.robot.disconnect()


# ── Scene camera ─────────────────────────────────────────────────────────────
class OpenCVCapture:
    """Opens one OpenCV USB camera at 640x480 and 30 fps.

    The device follows LeRobot's OpenCVCameraConfig `index_or_path` model:
    pass an integer camera index or a path such as /dev/video0.
    """

    def __init__(self, index_or_path=0):
        if isinstance(index_or_path, str) and index_or_path.startswith("/dev/"):
            if not os.path.exists(index_or_path):
                raise FileNotFoundError(
                    f"{index_or_path} does not exist. "
                    "Check with `v4l2-ctl --list-devices`."
                )

        cap = cv2.VideoCapture(index_or_path)
        if not cap.isOpened():
            raise RuntimeError(
                f"Could not open scene camera {index_or_path!r}. "
                "Check with `v4l2-ctl --list-devices`."
            )
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        self._cap     = cap
        self._color   = None
        self._lock    = threading.Lock()
        self._stop    = threading.Event()
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[Scene camera] Opened {index_or_path!r} with OpenCV")

    def _loop(self):
        err_count    = 0
        err_last_log = 0.0
        while not self._stop.is_set():
            try:
                ok, img = self._cap.read()
                if not ok:
                    raise RuntimeError("cv2.VideoCapture.read() returned no frame")
                with self._lock:
                    self._color = img
            except Exception as e:
                if not self._stop.is_set():
                    err_count += 1
                    now = time.monotonic()
                    if now - err_last_log > 10.0:
                        print(f"[Scene camera] capture error x{err_count}: {e}")
                        err_count    = 0
                        err_last_log = now
                    time.sleep(0.1)

    def get_latest_color(self):
        with self._lock:
            return self._color

    def release(self):
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._cap.release()
        print("[Scene camera] Released")


# ── Wrist camera ─────────────────────────────────────────────────────────────
FLIP_CHOICES = ["v", "h", "180", "none"]
_FLIP_CODES = {"v": 0, "h": 1, "180": -1}


class WristCamera:
    def __init__(self, cam_id, flip="180", enable_ae=False):
        self.cam_id = cam_id
        self.flip_code = _FLIP_CODES.get(flip)  # None for "none"
        self._cap = None
        self._ae = None

        dev = _v4l2_device(cam_id)
        if not os.path.exists(dev):
            present = sorted(p for p in os.listdir("/dev") if p.startswith("video"))
            raise FileNotFoundError(
                f"{dev} does not exist — wrist camera not connected. "
                f"Available video devices: {present}. "
                f"Check with `v4l2-ctl --list-devices`."
            )
        cap = cv2.VideoCapture(cam_id)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open wrist camera at index {cam_id}")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        # Lock white balance to a fixed temperature — auto WB drift between
        # sessions can collapse predicted action deltas to near zero.
        set_v4l2(
            cam_id,
            white_balance_automatic=0,
            white_balance_temperature=4600,
            auto_exposure=1,
            brightness=32,
        )
        self._cap = cap
        if enable_ae:
            self._ae = _AEController(cam_id)

    def read(self):
        self._cap.grab()  # flush stale buffered frame
        ok, img = self._cap.read()
        if not ok:
            return None
        if self.flip_code is not None:
            img = cv2.flip(img, self.flip_code)
        return img

    def update_observations(self, *, wrist_bgr=None, scene_bgr=None):
        if self._ae is not None:
            self._ae.update_observations(wrist_bgr=wrist_bgr, scene_bgr=scene_bgr)

    def close(self):
        if self._cap is None:
            return
        if self._ae is not None:
            self._ae.stop()
            self._ae.join(timeout=2.0)
            self._ae = None
        self._cap.release()
        self._cap = None
        reset_wrist_to_auto(self.cam_id)


class _AEController:
    """Adaptive brightness controller for cameras whose exposure_time_absolute
    is non-functional. Nudges the `brightness` v4l2 control on a slow loop to
    track a target intensity, optionally matching the scene-camera mean so
    both cameras stay matched as room lighting changes.
    """

    BRIGHTNESS_MIN, BRIGHTNESS_MAX = -32, 64
    TARGET_MIN, TARGET_MAX = 40.0, 100.0

    def __init__(self, cam_id, period_s=1.0):
        self.cam_id = cam_id
        self.period = period_s
        self.brightness = 32
        self.target = 70.0
        self._wrist_mean = None
        self._scene_mean = None
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def update_observations(self, *, wrist_bgr=None, scene_bgr=None):
        with self._lock:
            if wrist_bgr is not None:
                self._wrist_mean = float(np.mean(wrist_bgr))
            if scene_bgr is not None:
                self._scene_mean = float(np.mean(scene_bgr))

    def _loop(self):
        while not self._stop_evt.wait(self.period):
            with self._lock:
                wrist_mean = self._wrist_mean
                scene_mean = self._scene_mean
            if wrist_mean is None:
                continue
            if scene_mean is not None:
                self.target = float(np.clip(scene_mean, self.TARGET_MIN, self.TARGET_MAX))
            err = self.target - wrist_mean
            if abs(err) < 4.0:
                continue
            step = int(np.clip(np.sign(err) * max(1, abs(err) / 4), -8, 8))
            new_b = int(np.clip(self.brightness + step,
                                self.BRIGHTNESS_MIN, self.BRIGHTNESS_MAX))
            if new_b != self.brightness:
                self.brightness = new_b
                set_v4l2(self.cam_id, brightness=new_b)
                print(f"[Wrist AE] mean={wrist_mean:.1f} target={self.target:.1f} "
                      f"→ brightness={new_b}")

    def stop(self):
        self._stop_evt.set()

    def join(self, timeout=2.0):
        self._thread.join(timeout=timeout)


def warmup_cameras(wrist: "WristCamera", scene: "OpenCVCapture", timeout: float = 30.0) -> None:
    """Block until both cameras produce frames, or raise on timeout."""
    print("[MolmoAct] Warming up cameras (up to 30 s)...")
    t_start  = time.time()
    next_log = t_start + 2.0
    wrist_ok = scene_ok = False
    while time.time() - t_start < timeout:
        if not wrist_ok and wrist.read() is not None:
            wrist_ok = True
            print(f"[MolmoAct]   wrist ready ({time.time()-t_start:.1f}s)")
        if not scene_ok and scene.get_latest_color() is not None:
            scene_ok = True
            print(f"[MolmoAct]   scene ready ({time.time()-t_start:.1f}s)")
        if wrist_ok and scene_ok:
            return
        if time.time() > next_log:
            print(f"[MolmoAct]   waiting... wrist={wrist_ok} scene={scene_ok}")
            next_log = time.time() + 2.0
        time.sleep(0.1)
    raise RuntimeError(
        f"Cameras did not produce frames in {timeout:.0f}s "
        f"(wrist={wrist_ok}, scene={scene_ok}). Check USB connections and camera indexes."
    )
