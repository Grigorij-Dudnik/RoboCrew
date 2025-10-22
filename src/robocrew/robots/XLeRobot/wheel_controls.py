"""Lightweight wheel helpers for the XLeRobot."""

from __future__ import annotations

import time
from typing import Dict, Mapping, Optional

from src.robocrew.robots.XLeRobot.sdk import DEFAULT_BAUDRATE, ScsServoSDK

DEFAULT_SPEED = 10_000
LINEAR_MPS = 0.25
ANGULAR_DPS = 100.0

ACTION_MAP = {
    "up": {7: 1, 8: 0, 9: -1},
    "down": {7: -1, 8: 0, 9: 1},
    "left": {7: -1, 8: -1, 9: -1},
    "right": {7: 1, 8: 1, 9: 1},
}


class XLeRobotWheels:
    """Minimal wheel controller that keeps only basic movement helpers."""

    def __init__(
        self,
        sdk: ScsServoSDK,
        *,
        speed: int = DEFAULT_SPEED,
        action_map: Optional[Mapping[str, Mapping[int, int]]] = None,
    ) -> None:
        
        self.sdk = sdk
        self.speed = speed
        self.action_map = ACTION_MAP if action_map is None else action_map
        self._wheel_ids = tuple(sorted(next(iter(self.action_map.values())).keys()))

    def _write(self, action: str) -> Dict[int, int]:
        multipliers = self.action_map[action.lower()]
        payload = {wid: self.speed * factor for wid, factor in multipliers.items()}
        self.sdk.sync_write_wheel_speeds(payload)
        return payload

    def _stop(self) -> Dict[int, int]:
        payload = {wid: 0 for wid in self._wheel_ids}
        self.sdk.sync_write_wheel_speeds(payload)
        return payload

    def _run(self, action: str, duration: float) -> Dict[int, int]:
        if duration <= 0:
            return {}
        payload = self._write(action)
        time.sleep(duration)
        self._stop()
        return payload

    def go_forward(self, meters: float) -> Dict[int, int]:
        return self._run("up", float(meters) / LINEAR_MPS)

    def go_backward(self, meters: float) -> Dict[int, int]:
        return self._run("down", float(meters) / LINEAR_MPS)

    def turn_left(self, degrees: float) -> Dict[int, int]:
        return self._run("left", float(degrees) / ANGULAR_DPS)

    def turn_right(self, degrees: float) -> Dict[int, int]:
        return self._run("right", float(degrees) / ANGULAR_DPS)

    def apply_wheel_modes(self) -> None:
        for wid in self._wheel_ids:
            self.sdk.set_wheel_mode(wid)

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


