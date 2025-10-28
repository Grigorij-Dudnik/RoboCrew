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
        *,
        speed: int = DEFAULT_SPEED,
        action_map: Optional[Mapping[str, Mapping[str, int]]] = None,
    ) -> None:
        self.wheel_arm_usb = wheel_arm_usb
        self.speed = speed
        self.action_map = ACTION_MAP if action_map is None else action_map
        self._wheel_names = tuple(sorted(next(iter(self.action_map.values())).keys()))

        # Initialize FeetechMotorsBus with the three wheel motors
        self.bus = FeetechMotorsBus(
            port=wheel_arm_usb,
            motors={
                "base_left_wheel": Motor(7, "sts3215", MotorNormMode.RANGE_M100_100),
                "base_back_wheel": Motor(8, "sts3215", MotorNormMode.RANGE_M100_100),
                "base_right_wheel": Motor(9, "sts3215", MotorNormMode.RANGE_M100_100),
            },
        )
        self.bus.connect()
        self.apply_wheel_modes()

    def _write(self, action: str) -> Dict[str, int]:
        multipliers = self.action_map[action.lower()]
        payload = {name: self.speed * factor for name, factor in multipliers.items()}
        self.bus.sync_write("Goal_Velocity", payload)
        return payload

    def _stop(self) -> Dict[str, int]:
        payload = {name: 0 for name in self._wheel_names}
        self.bus.sync_write("Goal_Velocity", payload)
        return payload

    def _run(self, action: str, duration: float) -> Dict[str, int]:
        if duration <= 0:
            return {}
        payload = self._write(action)
        time.sleep(duration)
        self._stop()
        return payload

    def go_forward(self, meters: float) -> Dict[str, int]:
        return self._run("up", float(meters) / LINEAR_MPS)

    def go_backward(self, meters: float) -> Dict[str, int]:
        return self._run("down", float(meters) / LINEAR_MPS)

    def turn_left(self, degrees: float) -> Dict[str, int]:
        return self._run("left", float(degrees) / ANGULAR_DPS)

    def turn_right(self, degrees: float) -> Dict[str, int]:
        return self._run("right", float(degrees) / ANGULAR_DPS)

    def apply_wheel_modes(self) -> None:
        """Configure motors for wheel mode (velocity control)."""
        from lerobot.motors.feetech import OperatingMode

        for name in self._wheel_names:
            self.bus.write("Operating_Mode", name, OperatingMode.VELOCITY.value)

        self.bus.enable_torque()

    def disconnect(self) -> None:
        """Disconnect and cleanup."""
        self._stop()
        self.bus.disconnect()

    def __del__(self) -> None:
        """Ensure cleanup on destruction."""
        if hasattr(self, "bus") and self.bus.is_connected:
            self.disconnect()

