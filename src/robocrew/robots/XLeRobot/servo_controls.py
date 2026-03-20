"""Lightweight wheel helpers for the XLeRobot."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Literal, Mapping, Optional
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode


DEFAULT_SPEED = 10_000
LINEAR_MPS = 0.25
ANGULAR_DPS = 100.0

ACTION_MAP = {
    "forward": {7: 1.0, 8: 0.0, 9: -1.0},
    "backward": {7: -1.0, 8: 0.0, 9: 1.0},
    "strafe_left": {7: -0.15, 8: 1.0, 9: -0.15},
    "strafe_right": {7: 0.15, 8: -1.0, 9: 0.15},
    "turn_left": {7: 1.0, 8: 1.0, 9: 1.0},
    "turn_right": {7: -1.0, 8: -1.0, 9: -1.0},
}

HEAD_SERVO_MAP = {"yaw": 7, "pitch": 8}


def _pick_non_degree_norm_mode() -> MotorNormMode:
    for name in ("RANGE_0_4095", "RANGE_0_100", "RANGE_M100_100"):
        mode = getattr(MotorNormMode, name, None)
        if mode is not None:
            return mode
    for mode in MotorNormMode:
        if mode != MotorNormMode.DEGREES:
            return mode
    return MotorNormMode.DEGREES


POSITION_NORM_MODE = _pick_non_degree_norm_mode()
HEAD_NORM_MODE = MotorNormMode.DEGREES
HEAD_YAW_LIMIT_DEG = (-120.0, 120.0)
HEAD_PITCH_LIMIT_DEG = (0.0, 85.0)


def _clamp(value: float, bounds: tuple[float, float]) -> float:
    low, high = bounds
    return max(low, min(high, float(value)))


DEFAULT_ARM_SERVO_MAP = {
    "shoulder_pan": 1,
    "shoulder_lift": 2,
    "elbow_flex": 3,
    "wrist_flex": 4,
    "wrist_roll": 5,
    "gripper": 6,
}


def _load_arm_servo_map(file_name: str) -> Dict[str, int]:
    local_path = Path(__file__).resolve().with_name(file_name)
    repo_path = Path(__file__).resolve().parents[4] / file_name
    if local_path.exists() or repo_path.exists():
        source_path = local_path if local_path.exists() else repo_path
        config = json.loads(source_path.read_text(encoding="utf-8"))
        return {name: int(item["id"]) for name, item in config.items()}
    # Fallback for wheel installations that don't ship root-level arm json files.
    return DEFAULT_ARM_SERVO_MAP.copy()


ARM_SERVO_MAPS = {
    "left": _load_arm_servo_map("left_arm.json"),
    "right": _load_arm_servo_map("right_arm.json"),
}
DEFAULT_ARM_POSITION_DIR = "~/.cache/robocrew/positions/"
DEFAULT_ARM_CALIBRATION_DIR = "~/.cache/robocrew/calibrations/"


def _default_calibration(ids: tuple[int, ...]) -> Dict[int, MotorCalibration]:
    return {
        sid: MotorCalibration(
            id=sid,
            drive_mode=0,
            homing_offset=0,
            range_min=0,
            range_max=4095,
        )
        for sid in ids
    }


def _run_lerobot_calibrate(port: str, calibration_id: str, output_path: Path) -> None:
    env = dict(os.environ)
    env["HF_LEROBOT_CALIBRATION"] = str(Path(DEFAULT_ARM_CALIBRATION_DIR).expanduser())
    cmd = [
        sys.executable,
        "-m",
        "lerobot.scripts.lerobot_calibrate",
        "--robot.type=so101_follower",
        f"--robot.port={port}",
        f"--robot.id={calibration_id}",
    ]
    subprocess.run(cmd, check=True, env=env)
    generated = Path(env["HF_LEROBOT_CALIBRATION"]).expanduser() / "robots" / "so_follower" / f"{calibration_id}.json"
    if generated.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated, output_path)


def _load_arm_calibration(
    file_name: str,
    ids: tuple[int, ...],
    arm_usb_port: Optional[str] = None,
) -> Dict[int, MotorCalibration]:
    path = Path(DEFAULT_ARM_CALIBRATION_DIR).expanduser() / file_name
    if not path.exists():
        if arm_usb_port:
            calibration_id = Path(file_name).stem
            print(f"Calibration file '{path}' not found. Running LeRobot calibration for '{calibration_id}'...")
            try:
                _run_lerobot_calibrate(arm_usb_port, calibration_id, path)
            except Exception as exc:
                print(f"Warning: auto calibration failed for '{calibration_id}': {exc}")
        if not path.exists():
            print(f"Warning: calibration file still missing: '{path}'. Using default calibration.")
        return _default_calibration(ids)

    data = json.loads(path.read_text(encoding="utf-8"))
    loaded = {
        int(item["id"]): MotorCalibration(
            id=int(item["id"]),
            drive_mode=int(item.get("drive_mode", 0)),
            homing_offset=int(item.get("homing_offset", 0)),
            range_min=int(item.get("range_min", 0)),
            range_max=int(item.get("range_max", 4095)),
        )
        for item in data.values()
        if isinstance(item, dict) and "id" in item
    }
    for sid, cal in _default_calibration(ids).items():
        loaded.setdefault(sid, cal)
    return loaded

class ServoControler:
    """Minimal wheel controller that keeps only basic movement helpers."""

    def __init__(
        self,
        right_arm_wheel_usb: str = None,
        left_arm_head_usb: str = None,
        *,
        speed: int = DEFAULT_SPEED,
        action_map: Optional[Mapping[str, Mapping[int, float]]] = None,
    ) -> None:
        self.right_arm_wheel_usb = right_arm_wheel_usb
        self.left_arm_head_usb = left_arm_head_usb
        self.speed = speed
        self.action_map = ACTION_MAP if action_map is None else action_map
        self._wheel_ids = tuple(list(self.action_map.values())[0].keys())
        self._head_ids = tuple(HEAD_SERVO_MAP.values())
        self._right_arm_ids = tuple(ARM_SERVO_MAPS["right"].values())
        self._left_arm_ids = tuple(ARM_SERVO_MAPS["left"].values())
        self._arm_positions_right = {name: 0.0 for name in ARM_SERVO_MAPS["right"].keys()}
        self._arm_positions_left = {name: 0.0 for name in ARM_SERVO_MAPS["left"].keys()}
        self._arm_positions = {name: 0.0 for name in ARM_SERVO_MAPS["right"].keys()}
        right_arm_calibration = _load_arm_calibration("right_arm.json", self._right_arm_ids, right_arm_wheel_usb)
        left_arm_calibration = _load_arm_calibration("left_arm.json", self._left_arm_ids, left_arm_head_usb)

        # Initialize FeetechMotorsBus with the three wheel motors
        if right_arm_wheel_usb:
            arm_motors = {
                aid: Motor(aid, "sts3215", POSITION_NORM_MODE)
                for aid in self._right_arm_ids
            }
            self.wheel_bus = FeetechMotorsBus(
                port=right_arm_wheel_usb,
                motors={
                    **arm_motors,
                    7: Motor(7, "sts3215", MotorNormMode.RANGE_M100_100),
                    8: Motor(8, "sts3215", MotorNormMode.RANGE_M100_100),
                    9: Motor(9, "sts3215", MotorNormMode.RANGE_M100_100),
                },
                calibration=right_arm_calibration,
            )
            self.wheel_bus.connect()
            self.apply_wheel_modes()
            self.apply_arm_modes()
        
        # Create basic calibration for head motors
        head_calibration = {
            **left_arm_calibration,
            7: MotorCalibration(
                id=7,
                drive_mode=0,
                homing_offset=0,
                range_min=0,
                range_max=4095,
            ),
            8: MotorCalibration(
                id=8,
                drive_mode=0,
                homing_offset=0,
                range_min=0,
                range_max=4095,
            ),
        }
        
        # Initialize FeetechMotorsBus for head motors
        if left_arm_head_usb:
            left_arm_motors = {
                aid: Motor(aid, "sts3215", POSITION_NORM_MODE)
                for aid in self._left_arm_ids
            }
            self.head_bus = FeetechMotorsBus(
                port=left_arm_head_usb,
                motors={
                    **left_arm_motors,
                    HEAD_SERVO_MAP["yaw"]: Motor(HEAD_SERVO_MAP["yaw"], "sts3215", HEAD_NORM_MODE),
                    HEAD_SERVO_MAP["pitch"]: Motor(HEAD_SERVO_MAP["pitch"], "sts3215", HEAD_NORM_MODE),
                },
                calibration=head_calibration,
            )
            self.head_bus.connect()
            self.apply_head_modes()
            self.apply_arm_modes()
            self._head_positions = {HEAD_SERVO_MAP["yaw"]: 0.0, HEAD_SERVO_MAP["pitch"]: 0.0}


    def _wheels_stop(self) -> None:
        if not hasattr(self, "wheel_bus"):
            print("Warning: wheel bus not initialized, cannot stop wheels.")
            return
        payload = {wid: 0 for wid in self._wheel_ids}
        self.wheel_bus.sync_write("Goal_Velocity", payload)

    def _wheels_run(self, action: str, duration: float) -> None:
        if duration > 0:
            multipliers = self.action_map[action]
            payload = {wid: int(self.speed * factor) for wid, factor in multipliers.items()}
            self.wheel_bus.sync_write("Goal_Velocity", payload)
            time.sleep(duration)
            payload = {wid: 0 for wid in self._wheel_ids}
            self.wheel_bus.sync_write("Goal_Velocity", payload)

    def go_forward(self, meters: float) -> None:
        self._wheels_run("forward", float(meters) / LINEAR_MPS)

    def go_backward(self, meters: float) -> None:
        self._wheels_run("backward", float(meters) / LINEAR_MPS)

    def turn_left(self, degrees: float) -> None:
        self._wheels_run("turn_left", float(degrees) / ANGULAR_DPS)

    def turn_right(self, degrees: float) -> None:
        self._wheels_run("turn_right", float(degrees) / ANGULAR_DPS)
    
    def strafe_left(self, meters: float) -> None:
        self._wheels_run("strafe_left", float(meters) / LINEAR_MPS)
    
    def strafe_right(self, meters: float) -> None:
        self._wheels_run("strafe_right", float(meters) / LINEAR_MPS)

    def turn_head_to_vla_position(self, pitch_deg=45) -> str:
        self.turn_head_pitch(pitch_deg)
        self.turn_head_yaw(0)
        time.sleep(0.9)

    def reset_head_position(self) -> str:
        self.turn_head_pitch(22)
        self.turn_head_yaw(0)
        time.sleep(0.9)

    def apply_wheel_modes(self) -> None:
        for wid in self._wheel_ids:
            self.wheel_bus.write("Operating_Mode", wid, OperatingMode.VELOCITY.value)

        self.wheel_bus.enable_torque()

    def _set_position_mode(self, bus: FeetechMotorsBus, ids: tuple[int, ...]) -> None:
        for sid in ids:
            bus.write("Operating_Mode", sid, OperatingMode.POSITION.value)
        bus.enable_torque()

    def apply_arm_modes(self) -> None:
        if hasattr(self, "wheel_bus"):
            self._set_position_mode(self.wheel_bus, self._right_arm_ids)
        if hasattr(self, "head_bus"):
            self._set_position_mode(self.head_bus, self._left_arm_ids)

    def apply_head_modes(self) -> None:
        self._set_position_mode(self.head_bus, self._head_ids)

    def _set_bus_torque(self, bus: FeetechMotorsBus, ids: tuple[int, ...], enabled: bool) -> None:
        fn = getattr(bus, "enable_torque" if enabled else "disable_torque", None)
        if fn:
            fn()
            return
        for sid in ids:
            bus.write("Torque_Enable", sid, int(enabled))

    def _set_torque(self, enabled: bool, target: Literal["all", "wheels", "arms", "head"] = "all") -> None:
        groups = {
            "wheels": ((getattr(self, "wheel_bus", None), self._wheel_ids),),
            "head": ((getattr(self, "head_bus", None), self._head_ids),),
            "arms": (
                (getattr(self, "wheel_bus", None), self._right_arm_ids),
                (getattr(self, "head_bus", None), self._left_arm_ids),
            ),
        }
        selected = ("wheels", "head", "arms") if target == "all" else (target,)
        for key in selected:
            for bus, ids in groups[key]:
                if bus:
                    self._set_bus_torque(bus, ids, enabled)

    def enable_torque(self, target: Literal["all", "wheels", "arms", "head"] = "all") -> None:
        """Enable torque for all/wheels/arms/head."""
        self._set_torque(True, target)

    def disable_torque(self, target: Literal["all", "wheels", "arms", "head"] = "all") -> None:
        """Disable torque for all/wheels/arms/head."""
        self._set_torque(False, target)

    def turn_head_yaw(self, degrees: float) -> Dict[int, float]:
        payload = {HEAD_SERVO_MAP["yaw"]: _clamp(degrees, HEAD_YAW_LIMIT_DEG)}
        self.head_bus.sync_write("Goal_Position", payload)
        self._head_positions.update(payload)

    def turn_head_pitch(self, degrees: float) -> Dict[int, float]:
        payload = {HEAD_SERVO_MAP["pitch"]: _clamp(degrees, HEAD_PITCH_LIMIT_DEG)}
        self.head_bus.sync_write("Goal_Position", payload)
        self._head_positions.update(payload)

    def set_arm_position(self, positions: Mapping[str, float], arm_side: Literal["left", "right", "both"] = "both") -> Dict[str, float]:
        right_map = ARM_SERVO_MAPS["right"]
        left_map = ARM_SERVO_MAPS["left"]

        if arm_side in ("right", "both") and hasattr(self, "wheel_bus"):
            right_payload = {right_map[name]: float(value) for name, value in positions.items() if name in right_map}
            if right_payload:
                self.wheel_bus.sync_write("Goal_Position", right_payload)
                self._arm_positions_right.update({name: float(value) for name, value in positions.items() if name in right_map})

        if arm_side in ("left", "both") and hasattr(self, "head_bus"):
            left_payload = {left_map[name]: float(value) for name, value in positions.items() if name in left_map}
            if left_payload:
                self.head_bus.sync_write("Goal_Position", left_payload)
                self._arm_positions_left.update({name: float(value) for name, value in positions.items() if name in left_map})

        self._arm_positions.update({name: float(value) for name, value in positions.items()})
        return self._arm_positions.copy()

    def read_arm_present_position(self, arm_side: Literal["left", "right", "both"] = "both") -> Dict[str, float]:
        right_map = ARM_SERVO_MAPS["right"]
        left_map = ARM_SERVO_MAPS["left"]

        def _read_present(bus: FeetechMotorsBus, ids: tuple[int, ...]) -> Dict[int, float]:
            try:
                raw = bus.sync_read("Present_Position", list(ids))
                if isinstance(raw, dict):
                    return {int(k): float(v) for k, v in raw.items()}
                return {sid: float(value) for sid, value in zip(ids, raw)}
            except Exception:
                return {sid: float(bus.read("Present_Position", sid)) for sid in ids}

        if arm_side in ("right", "both") and hasattr(self, "wheel_bus"):
            right_data = _read_present(self.wheel_bus, self._right_arm_ids)
            self._arm_positions_right.update(
                {name: float(right_data[sid]) for name, sid in right_map.items() if sid in right_data}
            )

        if arm_side in ("left", "both") and hasattr(self, "head_bus"):
            left_data = _read_present(self.head_bus, self._left_arm_ids)
            self._arm_positions_left.update(
                {name: float(left_data[sid]) for name, sid in left_map.items() if sid in left_data}
            )

        self._arm_positions.update(self._arm_positions_left)
        self._arm_positions.update(self._arm_positions_right)
        if arm_side == "left":
            return self._arm_positions_left.copy()
        if arm_side == "right":
            return self._arm_positions_right.copy()
        return self._arm_positions.copy()

    def _arm_position_file(self, position_name: str, base_dir: str = DEFAULT_ARM_POSITION_DIR) -> Path:
        file_name = position_name if position_name.endswith(".json") else f"{position_name}.json"
        return Path(base_dir).expanduser() / file_name

    def save_arm_position(self, position_name: str = "arm_positions", arm_side: Literal["left", "right", "both"] = "both") -> str:
        if arm_side == "left":
            positions = self._arm_positions_left.copy()
        elif arm_side == "right":
            positions = self._arm_positions_right.copy()
        else:
            positions = {
                "left": self._arm_positions_left.copy(),
                "right": self._arm_positions_right.copy(),
            }
        data = {
            "arm_side": arm_side,
            "positions": positions,
        }
        file_path = self._arm_position_file(position_name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(file_path)

    def set_saved_position(self, position_name: str, arm_side: Literal["left", "right", "both"] = "both") -> Dict[str, float]:
        try:
            raw_data = json.loads(self._arm_position_file(position_name).read_text(encoding="utf-8"))
        except:
            return

        saved_side: Literal["left", "right", "both"]
        data: Dict[str, float] | Dict[str, Dict[str, float]]
        if isinstance(raw_data, dict) and "arm_side" in raw_data and "positions" in raw_data:
            saved_side = raw_data["arm_side"]
            data = raw_data["positions"]
        elif isinstance(raw_data, dict) and "left" in raw_data and "right" in raw_data:
            # Backward compatibility: old both-arm files had no metadata.
            saved_side = "both"
            data = raw_data
        else:
            raise ValueError(
                "Position file is missing arm-side metadata. Re-save the pose with a recent RoboCrew version."
            )

        if saved_side != arm_side:
            raise ValueError(
                f"Saved pose is for '{saved_side}' but requested '{arm_side}'. "
                "Use matching --arms value or re-save the pose."
            )

        if arm_side == "both":
            if isinstance(data, dict) and "left" in data and "right" in data:
                self.set_arm_position(data["left"], "left")
                return self.set_arm_position(data["right"], "right")
            return self.set_arm_position(data, "both")

        if isinstance(data, dict) and "left" in data and "right" in data:
            return self.set_arm_position(data[arm_side], arm_side)
        return self.set_arm_position(data, arm_side)

    def disconnect(self) -> None:
        if hasattr(self, 'wheel_bus'):
            self._wheels_stop()
            time.sleep(0.5)
            self.wheel_bus.disconnect()
        if hasattr(self, 'head_bus'):
            self.head_bus.disconnect()