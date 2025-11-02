"""Lightweight wheel helpers for the XLeRobot."""

from __future__ import annotations

import time
from typing import Dict, Mapping, Optional

from robocrew.robots.XLeRobot.sdk import DEFAULT_BAUDRATE, ScsServoSDK

DEFAULT_SPEED = 10_000
LINEAR_MPS = 0.25
ANGULAR_DPS = 100.0

ACTION_MAP = {
    "up": {7: 1, 8: 0, 9: -1},
    "down": {7: -1, 8: 0, 9: 1},
    "left": {7: -1, 8: -1, 9: -1},
    "right": {7: 1, 8: 1, 9: 1},
}

HEAD_SERVO_MAP = {"yaw": 7, "pitch": 8}


class XLeRobotWheels:
    """Minimal wheel controller that keeps only basic movement helpers."""

    def __init__(
        self,
        wheel_arm_usb: str = "/dev/arm_right",
        head_arm_usb: str = "/dev/arm_head",
        *,
        speed: int = DEFAULT_SPEED,
        action_map: Optional[Mapping[str, Mapping[int, int]]] = None,
    ) -> None:
        self.wheel_arm_usb = wheel_arm_usb
        self.head_arm_usb = head_arm_usb
        self.wheel_sdk = XLeRobotWheels.connect_serial(wheel_arm_usb, DEFAULT_BAUDRATE)
        self.head_sdk = XLeRobotWheels.connect_serial(head_arm_usb, DEFAULT_BAUDRATE)
        self.speed = speed
        self.action_map = ACTION_MAP if action_map is None else action_map
        self._wheel_ids = tuple(sorted(next(iter(self.action_map.values())).keys()))
        self._head_ids = tuple(sorted(HEAD_SERVO_MAP.values()))
        self._head_positions = self.head_sdk.sync_read_positions(list(self._head_ids))
        for sid in self._head_ids:
            self._head_positions.setdefault(sid, 2048)

    def _wheels_write(self, action: str) -> Dict[int, int]:
        multipliers = self.action_map[action.lower()]
        payload = {wid: self.speed * factor for wid, factor in multipliers.items()}
        self.wheel_sdk.sync_write_wheel_speeds(payload)
        return payload

    def _wheels_stop(self) -> Dict[int, int]:
        payload = {wid: 0 for wid in self._wheel_ids}
        self.wheel_sdk.sync_write_wheel_speeds(payload)
        return payload

    def _wheels_run(self, action: str, duration: float) -> Dict[int, int]:
        if duration <= 0:
            return {}
        payload = self._wheels_write(action)
        time.sleep(duration)
        self._wheels_stop()
        return payload

    def go_forward(self, meters: float) -> Dict[int, int]:
        return self._wheels_run("up", float(meters) / LINEAR_MPS)

    def go_backward(self, meters: float) -> Dict[int, int]:
        return self._wheels_run("down", float(meters) / LINEAR_MPS)

    def turn_left(self, degrees: float) -> Dict[int, int]:
        return self._wheels_run("left", float(degrees) / ANGULAR_DPS)

    def turn_right(self, degrees: float) -> Dict[int, int]:
        return self._wheels_run("right", float(degrees) / ANGULAR_DPS)

    def apply_wheel_modes(self) -> None:
        for wid in self._wheel_ids:
            self.wheel_sdk.set_wheel_mode(wid)

    def turn_head_yaw(self, degrees: float) -> Dict[int, int]:
        position = self._degrees_to_position(degrees)
        payload = {HEAD_SERVO_MAP["yaw"]: position}
        self.head_sdk.sync_write_positions(payload)
        self._head_positions.update(payload)
        return payload

    def turn_head_pitch(self, degrees: float) -> Dict[int, int]:
        position = self._degrees_to_position(degrees)
        payload = {HEAD_SERVO_MAP["pitch"]: position}
        self.head_sdk.sync_write_positions(payload)
        self._head_positions.update(payload)
        return payload

    @staticmethod
    def _degrees_to_position(degrees: float) -> int:
        wrapped = float(degrees) % 360.0
        scale = wrapped / 360.0
        return max(0, min(4095, int(round(scale * 4095))))

    @staticmethod
    def connect_serial(
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        protocol_end: int = 0,
    ) -> ScsServoSDK:
        sdk = ScsServoSDK()
        if not sdk.connect(port, baudrate, protocol_end):
            raise RuntimeError(f"Failed to open serial port {port} @ {baudrate}")
        return sdk


