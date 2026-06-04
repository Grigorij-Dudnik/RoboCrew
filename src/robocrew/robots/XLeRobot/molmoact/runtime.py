"""
runtime.py — async producer/consumer with temporal ensembling for live
MolmoAct2 inference on the SO-101.

Two threads owned by AsyncPolicyRunner:

    InferenceProducer ─writes─► ChunkRingBuffer ◄─reads─ ExecutionConsumer
                                                               │
                           arm_state ◄──get_state── follower   │
                                                               ▼
                                                          set_target

Producer captures fresh observations and runs predict_chunk as fast as the
GPU allows. Each emitted chunk lands in a ring buffer tagged with the publish
wall-clock time (t_start).

Consumer ticks at exec_hz. On each tick it finds every chunk whose prediction
window covers "now", takes the in-chunk step index, and computes a weighted
average of those per-chunk actions with weights exp(-ensemble_m * age_seconds).
This is the ACT temporal-ensembling formulation (Zhao et al. 2023) adapted to
async inference.

NOTE: decoupled from the torch-based policy module — `policy` is any object with
a predict_chunk(images, state, prompt, *, num_steps, cuda_graph) method (e.g.
the RemotePolicyClient). ACTION_FPS is defined locally so the robot box never
imports torch.
"""
import collections
import os
import threading
import time
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from .frame_transforms import JOINT_COUNT, clip_action

# Rate at which the model's chunk is meant to play back. Training data is
# 30 fps, so chunk[k] is meant for t_start + k/30 seconds.
ACTION_FPS = 30.0


def _bgr_to_pil(img_bgr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))


@dataclass
class RuntimeConfig:
    """All knobs that affect producer/consumer behaviour."""
    prompt: str
    exec_hz: float = 30.0
    max_step_deg: float = 15.0
    actions_per_chunk: Optional[int] = None
    smooth_alpha: float = 1.0
    ensemble_m: float = 0.5
    warmup_predictions: int = 0
    num_steps: int = 10
    cuda_graph: bool = False
    scene_only: bool = False
    save_frames_dir: Optional[str] = None
    dry_run: bool = False


class ChunkRingBuffer:
    """Thread-safe ring of the most recent chunks for temporal ensembling.

    Each entry is (chunk, t_start, chunk_id):
      - chunk: (T, JOINT_COUNT) action plan in arm frame.
      - t_start: monotonic wall-clock time when the chunk became executable.
      - chunk_id: monotonically increasing diagnostic counter.
    """

    def __init__(self, capacity: int = 6):
        self._lock    = threading.Lock()
        self._entries = collections.deque(maxlen=capacity)
        self._next_id = 1

    def add(self, chunk: np.ndarray, t_start: float) -> int:
        with self._lock:
            chunk_id = self._next_id
            self._next_id += 1
            self._entries.append((chunk, t_start, chunk_id))
            return chunk_id

    def snapshot(self):
        with self._lock:
            return list(self._entries)


class FrameBuffer:
    """Thread-safe latest-frames cache for cv2.imshow on the main thread."""

    def __init__(self):
        self._lock  = threading.Lock()
        self._wrist = None
        self._scene = None

    def set(self, wrist_bgr, scene_bgr):
        with self._lock:
            self._wrist = wrist_bgr
            self._scene = scene_bgr

    def get(self):
        with self._lock:
            return self._wrist, self._scene


class _InferenceProducer(threading.Thread):
    """Continuously runs predict_chunk and pushes each result to the ring."""

    def __init__(self, *, policy, follower, wrist, scene,
                 ring: ChunkRingBuffer, frame_buffer: FrameBuffer,
                 signs: np.ndarray, offsets: np.ndarray,
                 joint_min: np.ndarray, joint_max: np.ndarray,
                 config: RuntimeConfig):
        super().__init__(daemon=True, name="InferenceProducer")
        self.policy       = policy
        self.follower     = follower
        self.wrist        = wrist
        self.scene        = scene
        self.ring         = ring
        self.frame_buffer = frame_buffer
        self.signs        = signs
        self.offsets      = offsets
        self.joint_min    = joint_min
        self.joint_max    = joint_max
        self.config       = config
        self._stop_event  = threading.Event()

    def stop(self):
        self._stop_event.set()

    def _capture(self):
        wrist_bgr = self.wrist.read()
        scene_bgr = self.scene.get_latest_color()
        if wrist_bgr is None or scene_bgr is None:
            return None, None, None
        self.wrist.update_observations(wrist_bgr=wrist_bgr, scene_bgr=scene_bgr)
        self.frame_buffer.set(wrist_bgr, scene_bgr)
        arm_state = self.follower.get_state().astype(np.float32)
        return wrist_bgr, scene_bgr, arm_state

    def _save_inputs(self, frames_bgr):
        if not self.config.save_frames_dir:
            return
        ts = int(time.time() * 1000)
        for i, im in enumerate(frames_bgr):
            cv2.imwrite(
                os.path.join(self.config.save_frames_dir, f"{ts:013d}_in{i}.jpg"),
                im,
            )

    def _postprocess(self, actions: np.ndarray) -> np.ndarray:
        """Convert model-frame chunk to arm frame and apply hard joint limits."""
        if actions.shape[1] != JOINT_COUNT:
            raise RuntimeError(
                f"Unexpected action shape {actions.shape}, expected (T, {JOINT_COUNT})"
            )
        actions = (actions - self.offsets) * self.signs  # model → arm frame
        return np.clip(actions, self.joint_min, self.joint_max)

    def run(self):
        cfg      = self.config
        pred_idx = 0
        while not self._stop_event.is_set():
            try:
                wrist_bgr, scene_bgr, arm_state = self._capture()
                if wrist_bgr is None:
                    time.sleep(0.05)
                    continue

                model_inputs_bgr = (
                    [scene_bgr, scene_bgr] if cfg.scene_only
                    else [scene_bgr, wrist_bgr]
                )
                self._save_inputs(model_inputs_bgr)

                state = self.signs * arm_state + self.offsets  # arm → model frame

                t0    = time.perf_counter()
                raw_actions = self.policy.predict_chunk(
                    images=[_bgr_to_pil(im) for im in model_inputs_bgr],
                    state=state,
                    prompt=cfg.prompt,
                    num_steps=cfg.num_steps,
                    cuda_graph=cfg.cuda_graph,
                )
                dt_ms = (time.perf_counter() - t0) * 1000.0

                actions = self._postprocess(raw_actions)

                pred_idx += 1
                if pred_idx <= cfg.warmup_predictions:
                    print(f"[Producer] warm-up {pred_idx}/{cfg.warmup_predictions} "
                          f"({dt_ms:.0f} ms) — not publishing")
                    continue

                chunk_id = self.ring.add(actions, time.monotonic())
                a0_d = actions[0] - arm_state
                print(
                    f"[Producer] {dt_ms:.0f} ms  id={chunk_id}  "
                    f"a0={np.round(actions[0], 1).tolist()}  "
                    f"Δ={np.round(a0_d, 1).tolist()}"
                )
            except Exception as e:
                print(f"[Producer] {type(e).__name__}: {e}")
                time.sleep(0.1)


class _ExecutionConsumer(threading.Thread):
    """Ticks at exec_hz; ensembles active chunks and sends one target per tick."""

    def __init__(self, *, follower, ring: ChunkRingBuffer, config: RuntimeConfig):
        super().__init__(daemon=True, name="ExecutionConsumer")
        self.follower         = follower
        self.ring             = ring
        self.exec_hz          = config.exec_hz
        self.max_step_deg     = config.max_step_deg
        self.actions_per_chunk = config.actions_per_chunk
        self.smooth_alpha     = float(np.clip(config.smooth_alpha, 0.05, 1.0))
        self.ensemble_m       = float(config.ensemble_m)
        self._last_sent       = None
        self._stop_event      = threading.Event()
        print(f"[Consumer] temporal ensembling  weight=exp(-{self.ensemble_m:.2f}*age_s)  "
              f"exec_hz={self.exec_hz:.0f}")
        if self.smooth_alpha < 1.0:
            print(f"[Consumer] post-ensemble EMA  alpha={self.smooth_alpha:.2f}")

    def stop(self):
        self._stop_event.set()

    def run(self):
        interval = 1.0 / self.exec_hz
        seen_ids = set()
        holding  = False
        while not self._stop_event.is_set():
            now     = time.monotonic()
            entries = self.ring.snapshot()

            active_actions = []
            active_ages    = []
            for chunk, t_start, chunk_id in entries:
                n = chunk.shape[0]
                if self.actions_per_chunk is not None:
                    n = min(n, self.actions_per_chunk)
                step = int((now - t_start) * ACTION_FPS)
                if 0 <= step < n:
                    active_actions.append(chunk[step])
                    active_ages.append(now - t_start)
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        print(f"[Consumer] chunk {chunk_id} active  "
                              f"step={step}/{n}  age={(now - t_start)*1000:.0f}ms")

            if not active_actions:
                if not holding:
                    print("[Consumer] no active chunks — holding last action")
                    holding = True
                time.sleep(interval)
                continue
            holding = False

            ages        = np.asarray(active_ages, dtype=np.float32)
            weights     = np.exp(-self.ensemble_m * ages)
            weights    /= weights.sum()
            actions_arr = np.stack(active_actions, axis=0)
            target      = (weights[:, None] * actions_arr).sum(axis=0).astype(np.float32)

            cur    = self.follower.get_state().astype(np.float32)
            target = clip_action(target, cur, self.max_step_deg)

            if self._last_sent is not None and self.smooth_alpha < 1.0:
                target = (self.smooth_alpha * target
                          + (1.0 - self.smooth_alpha) * self._last_sent)

            self._last_sent = target
            self.follower.set_target(target)
            time.sleep(interval)


class AsyncPolicyRunner:
    """Owns the inference producer and execution consumer threads.

    Usage:
        with AsyncPolicyRunner(policy=..., follower=..., wrist=..., scene=...,
                               signs=..., offsets=...,
                               joint_min=..., joint_max=...,
                               config=...) as runner:
            # main thread: show cameras or just wait
    """

    def __init__(self, *, policy, follower, wrist, scene,
                 signs: np.ndarray, offsets: np.ndarray,
                 joint_min: np.ndarray, joint_max: np.ndarray,
                 config: RuntimeConfig):
        self.ring         = ChunkRingBuffer()
        self.frame_buffer = FrameBuffer()
        self._producer = _InferenceProducer(
            policy=policy, follower=follower, wrist=wrist, scene=scene,
            ring=self.ring, frame_buffer=self.frame_buffer,
            signs=signs, offsets=offsets,
            joint_min=joint_min, joint_max=joint_max,
            config=config,
        )
        self._consumer = (None if config.dry_run
                          else _ExecutionConsumer(
                              follower=follower,
                              ring=self.ring,
                              config=config,
                          ))

    def start(self) -> "AsyncPolicyRunner":
        self._producer.start()
        if self._consumer is not None:
            self._consumer.start()
        return self

    def stop(self, join_timeout: float = 2.0) -> None:
        if self._consumer is not None:
            self._consumer.stop()
        self._producer.stop()
        if self._consumer is not None:
            self._consumer.join(timeout=join_timeout)
        self._producer.join(timeout=join_timeout)

    def latest_frames(self):
        """Returns (wrist_bgr, scene_bgr) from the last producer capture."""
        return self.frame_buffer.get()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False
