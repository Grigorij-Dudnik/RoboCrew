"""Lightweight wheel helpers for the XLeRobot."""

from __future__ import annotations

import time
from typing import Dict, Mapping, Optional

from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus

DEFAULT_BAUDRATE = 1_000_000
DEFAULT_SPEED = 10_000
LINEAR_MPS = 0.25
ANGULAR_DPS = 100.0

ACTION_MAP = {
    "up": {"base_left_wheel": 1, "base_back_wheel": 0, "base_right_wheel": -1},
    "down": {"base_left_wheel": -1, "base_back_wheel": 0, "base_right_wheel": 1},
    "left": {"base_left_wheel": -1, "base_back_wheel": -1, "base_right_wheel": -1},
    "right": {"base_left_wheel": 1, "base_back_wheel": 1, "base_right_wheel": 1},
}


class XLeRobotWheels:
    """Minimal wheel controller that keeps only basic movement helpers."""

    def __init__(
        self,
        wheel_arm_usb: str = "/dev/arm_right",
        head_arm_usb: str = "/dev/arm_head",
        *,
        speed: int = DEFAULT_SPEED,
        action_map: Optional[Mapping[str, Mapping[str, int]]] = None,
    ) -> None:
        self.wheel_arm_usb = wheel_arm_usb
        self.head_arm_usb = head_arm_usb
        self.speed = speed
        self.action_map = ACTION_MAP if action_map is None else action_map
        self._wheel_names = tuple(sorted(next(iter(self.action_map.values())).keys()))
        self._head_names = ("yaw", "pitch")
        
        # Initialize FeetechMotorsBus with the three wheel motors
        self.wheel_bus = FeetechMotorsBus(
            port=wheel_arm_usb,
            motors={
                "base_left_wheel": Motor(7, "sts3215", MotorNormMode.RANGE_M100_100),
                "base_back_wheel": Motor(8, "sts3215", MotorNormMode.RANGE_M100_100),
                "base_right_wheel": Motor(9, "sts3215", MotorNormMode.RANGE_M100_100),
            },
        )
        self.wheel_bus.connect()
        self.apply_wheel_modes()
        
        # Initialize FeetechMotorsBus for head motors
        self.head_bus = FeetechMotorsBus(
            port=head_arm_usb,
            motors={
                "yaw": Motor(7, "sts3215", MotorNormMode.DEGREES),
                "pitch": Motor(8, "sts3215", MotorNormMode.DEGREES),
            },
        )
        self.head_bus.connect()
        self.apply_head_modes()

    def _wheels_write(self, action: str) -> Dict[str, int]:
        multipliers = self.action_map[action.lower()]
        payload = {name: self.speed * factor for name, factor in multipliers.items()}
        self.wheel_bus.sync_write("Goal_Velocity", payload)
        return payload

    def _wheels_run(self, action: str, duration: float) -> Dict[str, int]:
        if duration <= 0:
            return {}
        payload = self._wheels_write(action)
        time.sleep(duration)
        self._wheels_stop()
        return payload

    def go_forward(self, meters: float) -> Dict[str, int]:
        return self._wheels_run("up", float(meters) / LINEAR_MPS)

    def go_backward(self, meters: float) -> Dict[str, int]:
        return self._wheels_run("down", float(meters) / LINEAR_MPS)

    def turn_left(self, degrees: float) -> Dict[str, int]:
        return self._wheels_run("left", float(degrees) / ANGULAR_DPS)

    def turn_right(self, degrees: float) -> Dict[str, int]:
        return self._wheels_run("right", float(degrees) / ANGULAR_DPS)

    def apply_wheel_modes(self) -> None:
        """Configure motors for wheel mode (velocity control)."""
        from lerobot.motors.feetech import OperatingMode

        for name in self._wheel_names:
            self.wheel_bus.write("Operating_Mode", name, OperatingMode.VELOCITY.value)

        self.wheel_bus.enable_torque()

    def apply_head_modes(self) -> None:
        """Configure head motors for position mode."""
        from lerobot.motors.feetech import OperatingMode

        for name in self._head_names:
            self.head_bus.write("Operating_Mode", name, OperatingMode.POSITION.value)

        self.head_bus.enable_torque()

    def turn_head_yaw(self, degrees: float) -> Dict[str, float]:
        """Turn head yaw to specified degrees."""
        payload = {"yaw": float(degrees)}
        self.head_bus.sync_write("Goal_Position", payload)
        return payload

    def turn_head_pitch(self, degrees: float) -> Dict[str, float]:
        """Turn head pitch to specified degrees."""
        payload = {"pitch": float(degrees)}
        self.head_bus.sync_write("Goal_Position", payload)
        return payload

    def get_head_position(self) -> Dict[str, float]:
        """Get current head motor positions in degrees."""
        return self.head_bus.sync_read("Present_Position", list(self._head_names))

    def _wheels_stop(self) -> None:
        """Stop all wheel motors."""
        payload = {name: 0 for name in self._wheel_names}
        self.wheel_bus.sync_write("Goal_Velocity", payload)

    def disconnect(self) -> None:
        """Disconnect and cleanup."""
        self._wheels_stop()
        self.wheel_bus.disconnect()
        self.head_bus.disconnect()

    def __del__(self) -> None:
        """Ensure cleanup on destruction."""
        if hasattr(self, "wheel_bus") and self.wheel_bus.is_connected:
            self.disconnect()

