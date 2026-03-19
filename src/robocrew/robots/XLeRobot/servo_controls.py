"""Lightweight wheel helpers for the XLeRobot."""

from __future__ import annotations

import json
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


def _load_arm_servo_map(file_name: str) -> Dict[str, int]:
    config = json.loads((Path(__file__).resolve().parents[4] / file_name).read_text(encoding="utf-8"))
    return {name: int(item["id"]) for name, item in config.items()}


ARM_SERVO_MAPS = {
    "left": _load_arm_servo_map("left_arm.json"),
    "right": _load_arm_servo_map("right_arm.json"),
}
DEFAULT_ARM_POSITION_DIR = "~/.cache/robocrew/positions/"

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

        # Initialize FeetechMotorsBus with the three wheel motors
        if right_arm_wheel_usb:
            arm_motors = {
                aid: Motor(aid, "sts3215", MotorNormMode.DEGREES)
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
            )
            self.wheel_bus.connect()
            self.apply_wheel_modes()
            self.apply_arm_modes()
        
        # Create basic calibration for head motors
        # STS3215 motors have 4096 positions (0-4095) which typically map to ~360 degrees
        head_calibration = {
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
                aid: Motor(aid, "sts3215", MotorNormMode.DEGREES)
                for aid in self._left_arm_ids
            }
            self.head_bus = FeetechMotorsBus(
                port=left_arm_head_usb,
                motors={
                    **left_arm_motors,
                    HEAD_SERVO_MAP["yaw"]: Motor(HEAD_SERVO_MAP["yaw"], "sts3215", MotorNormMode.DEGREES),
                    HEAD_SERVO_MAP["pitch"]: Motor(HEAD_SERVO_MAP["pitch"], "sts3215", MotorNormMode.DEGREES),
                },
                calibration=head_calibration,
            )
            self.head_bus.connect()
            self.apply_head_modes()
            self.apply_arm_modes()
            self._head_positions = {HEAD_SERVO_MAP["yaw"]: 0.0, HEAD_SERVO_MAP["pitch"]: 0.0}


    def _wheels_stop(self) -> None:
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

    def turn_head_yaw(self, degrees: float) -> Dict[int, float]:
        payload = {HEAD_SERVO_MAP["yaw"]: float(degrees)}
        self.head_bus.sync_write("Goal_Position", payload)
        self._head_positions.update(payload)

    def turn_head_pitch(self, degrees: float) -> Dict[int, float]:
        payload = {HEAD_SERVO_MAP["pitch"]: float(degrees)}
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

    def _arm_position_file(self, position_name: str, base_dir: str = DEFAULT_ARM_POSITION_DIR) -> Path:
        file_name = position_name if position_name.endswith(".json") else f"{position_name}.json"
        return Path(base_dir).expanduser() / file_name

    def save_arm_position(self, position_name: str = "arm_positions", arm_side: Literal["left", "right", "both"] = "both") -> str:
        if arm_side == "left":
            data = self._arm_positions_left.copy()
        elif arm_side == "right":
            data = self._arm_positions_right.copy()
        else:
            data = {
                "left": self._arm_positions_left.copy(),
                "right": self._arm_positions_right.copy(),
            }
        file_path = self._arm_position_file(position_name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return str(file_path)

    def read_arm_position(self, position_name: str, arm_side: Literal["left", "right", "both"] = "both") -> Dict[str, float]:
        data = json.loads(self._arm_position_file(position_name).read_text(encoding="utf-8"))
        if arm_side == "both":
            if isinstance(data, dict) and "left" in data and "right" in data:
                self.set_arm_position(data["left"], "left")
                return self.set_arm_position(data["right"], "right")
            return self.set_arm_position(data, "both")

        if isinstance(data, dict) and "left" in data and "right" in data:
            return self.set_arm_position(data[arm_side], arm_side)
        return self.set_arm_position(data, arm_side)

    def disconnect(self) -> None:
        self._wheels_stop()
        time.sleep(0.5)
        if hasattr(self, 'wheel_bus'):
            self.wheel_bus.disconnect()
        if hasattr(self, 'head_bus'):
            self.head_bus.disconnect()