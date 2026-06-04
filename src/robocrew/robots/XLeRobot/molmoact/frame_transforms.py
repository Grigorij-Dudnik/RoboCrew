"""
frame_transforms.py — joint frame conversion helpers and safety clamps.

The SO-101 arm reports joint angles in one convention; the public LeRobot
SO-100/101 datasets that MolmoAct2 was trained on use a slightly different
one (sign flip on shoulder_lift, +90° offset on shoulder_lift and elbow_flex).
This is the official v3.0 → v2.1 conversion documented at:
    https://huggingface.co/docs/lerobot/backwardcomp

The conversion is two lines of arithmetic, kept inline at call sites:
    state_model_frame = signs * arm_state + offsets
    action_arm_frame  = (model_action - offsets) * signs
"""
import numpy as np

JOINT_COUNT = 6


def parse_joint_offsets(s: str) -> np.ndarray:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != JOINT_COUNT:
        raise ValueError(f"joint offsets need {JOINT_COUNT} values, got {len(parts)}: {s!r}")
    return np.asarray(parts, dtype=np.float32)


def parse_joint_signs(s: str) -> np.ndarray:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != JOINT_COUNT:
        raise ValueError(f"joint signs need {JOINT_COUNT} values, got {len(parts)}: {s!r}")
    arr = np.asarray(parts, dtype=np.float32)
    if not np.all(np.isin(arr, [-1.0, 1.0])):
        raise ValueError(f"joint signs must be +1 or -1, got {parts}")
    return arr


def parse_joint_limits(s, default_value) -> np.ndarray:
    """Parse a comma-separated limit string; 'none' skips that joint."""
    if s is None:
        return np.full(JOINT_COUNT, default_value, dtype=np.float32)
    parts = s.split(",")
    if len(parts) != JOINT_COUNT:
        raise ValueError(f"joint limits need {JOINT_COUNT} values, got {len(parts)}")
    out = np.full(JOINT_COUNT, default_value, dtype=np.float32)
    for i, p in enumerate(parts):
        if p.strip().lower() != "none":
            out[i] = float(p)
    return out


def clip_action(action: np.ndarray, current_state: np.ndarray,
                max_step_deg: float) -> np.ndarray:
    """Scale action so no joint moves more than max_step_deg in one tick.

    If the largest joint delta exceeds the cap, the entire delta vector is
    scaled down proportionally (direction preserved, magnitude reduced).
    """
    delta = action - current_state
    biggest = float(np.max(np.abs(delta)))
    if biggest <= max_step_deg or biggest == 0.0:
        return action
    return current_state + delta * (max_step_deg / biggest)
