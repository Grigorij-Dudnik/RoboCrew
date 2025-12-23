"""Lightweight wheel helpers for the XLeRobot."""

from __future__ import annotations

import time
from typing import Dict, Mapping, Optional
from lerobot.motors import Motor, MotorCalibration, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus, OperatingMode


DEFAULT_BAUDRATE = 1_000_000
DEFAULT_SPEED = 10_000
LINEAR_MPS = 0.25
ANGULAR_DPS = 90.0

ACTION_MAP = {
    "forward": {7: 1.0, 8: 0.0, 9: -1.0},
    "backward": {7: -1.0, 8: 0.0, 9: 1.0},
    "strafe_left": {7: -0.15, 8: 1.0, 9: -0.15},
    "strafe_right": {7: 0.15, 8: -1.0, 9: 0.15},
    "turn_left": {7: 1.0, 8: 1.0, 9: 1.0},
    "turn_right": {7: -1.0, 8: -1.0, 9: -1.0},
}

HEAD_SERVO_MAP = {"yaw": 7, "pitch": 8}


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

        # Initialize FeetechMotorsBus with the three wheel motors
        if right_arm_wheel_usb:
            self.wheel_bus = FeetechMotorsBus(
                port=right_arm_wheel_usb,
                motors={
                    7: Motor(7, "sts3215", MotorNormMode.RANGE_M100_100),
                    8: Motor(8, "sts3215", MotorNormMode.RANGE_M100_100),
                    9: Motor(9, "sts3215", MotorNormMode.RANGE_M100_100),
                },
            )
            self.wheel_bus.connect()
            self.apply_wheel_modes()
        
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
            self.head_bus = FeetechMotorsBus(
                port=left_arm_head_usb,
                motors={
                    HEAD_SERVO_MAP["yaw"]: Motor(HEAD_SERVO_MAP["yaw"], "sts3215", MotorNormMode.DEGREES),
                    HEAD_SERVO_MAP["pitch"]: Motor(HEAD_SERVO_MAP["pitch"], "sts3215", MotorNormMode.DEGREES),
                },
                calibration=head_calibration,
            )
            self.head_bus.connect()
            self.apply_head_modes()
            self._head_positions = None


    def _wheels_stop(self) -> None:
        payload = {wid: 0 for wid in self._wheel_ids}
        self.wheel_bus.sync_write("Goal_Velocity", payload)

    def _wheels_run(self, action: str, duration: float) -> Dict[int, int]:
        if duration > 0:
            multipliers = self.action_map[action]
            payload = {wid: int(self.speed * factor) for wid, factor in multipliers.items()}
            self.wheel_bus.sync_write("Goal_Velocity", payload)
            time.sleep(duration)
            payload = {wid: 0 for wid in self._wheel_ids}
            self.wheel_bus.sync_write("Goal_Velocity", payload)

    def go_forward(self, meters: float) -> Dict[int, int]:
        self._wheels_run("forward", float(meters) / LINEAR_MPS)

    def go_backward(self, meters: float) -> Dict[int, int]:
        self._wheels_run("backward", float(meters) / LINEAR_MPS)

    def turn_left(self, degrees: float) -> Dict[int, int]:
        self._wheels_run("turn_left", float(degrees) / ANGULAR_DPS)

    def turn_right(self, degrees: float) -> Dict[int, int]:
        self._wheels_run("turn_right", float(degrees) / ANGULAR_DPS)
    
    def strafe_left(self, meters: float) -> Dict[int, int]:
        self._wheels_run("strafe_left", float(meters) / LINEAR_MPS)
    
    def strafe_right(self, meters: float) -> Dict[int, int]:
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

    def apply_head_modes(self) -> None:
        for id in self._head_ids:
            self.head_bus.write("Operating_Mode", id, OperatingMode.POSITION.value)
        self.head_bus.enable_torque()

    def turn_head_yaw(self, degrees: float) -> Dict[int, float]:
        payload = {HEAD_SERVO_MAP["yaw"]: float(degrees)}
        self.head_bus.sync_write("Goal_Position", payload)
        self._head_positions.update(payload)

    def turn_head_pitch(self, degrees: float) -> Dict[int, float]:
        payload = {HEAD_SERVO_MAP["pitch"]: float(degrees)}
        self.head_bus.sync_write("Goal_Position", payload)
        self._head_positions.update(payload)

    def disconnect(self) -> None:
        self._wheels_stop()
        time.sleep(0.5)
        if hasattr(self, 'wheel_bus'):
            self.wheel_bus.disconnect()
        if hasattr(self, 'head_bus'):
            self.head_bus.disconnect()

