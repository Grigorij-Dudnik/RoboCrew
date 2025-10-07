
"""High-level wheel helpers for the XLe robot.

The original setup pulled its configuration from ``dual_mapper_config.json``.
To simplify deployment the relevant wheel parameters now live directly in this
module so there is no external configuration file dependency.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Tuple, Union

from sdk import DEFAULT_BAUDRATE, ScsServoSDK


# ---------------------------------------------------------------------------
# Default wheel configuration (was ``portB.wheel`` in dual_mapper_config.json)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WheelCalibration:
    """Direction multipliers applied to the configured base speed."""

    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0

    @classmethod
    def from_mapping(cls, data: Mapping[str, int]) -> "WheelCalibration":
        return cls(
            up=int(data.get("Up", 0)),
            down=int(data.get("Down", 0)),
            left=int(data.get("Left", 0)),
            right=int(data.get("Right", 0)),
        )

    def value_for(self, action: str) -> int:
        lookup = {
            "up": self.up,
            "down": self.down,
            "left": self.left,
            "right": self.right,
        }
        return lookup.get(action.lower(), 0)


@dataclass(frozen=True)
class WheelSpec:
    """Single wheel definition with its role and calibration."""

    id: int
    role: str = "both"
    calibration: WheelCalibration = field(default_factory=WheelCalibration)

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> Optional["WheelSpec"]:
        wid = int(data.get("id", 0))
        if wid <= 0:
            return None
        role = str(data.get("role", "both")).lower()
        raw_cal = data.get("calibration", {})
        if isinstance(raw_cal, Mapping):
            calibration = WheelCalibration.from_mapping(raw_cal)
        else:
            calibration = WheelCalibration()
        return cls(id=wid, role=role, calibration=calibration)

    def allows(self, action: str) -> bool:
        action = action.lower()
        if self.role == "both":
            return action in ("up", "down", "left", "right")
        if self.role == "drive":
            return action in ("up", "down")
        if self.role == "steer":
            return action in ("left", "right")
        return False

    def speed_for(self, action: str, base_speed: int) -> int:
        if not self.allows(action):
            return 0
        return self.calibration.value_for(action) * base_speed


@dataclass(frozen=True)
class WheelConfig:
    """Full wheel configuration shared by all actions."""

    speed: int
    meters_per_second: float
    degrees_per_second: float
    wheels: Tuple[WheelSpec, ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "WheelConfig":
        speed = int(data.get("speed", DEFAULT_WHEEL_CONFIG.speed))
        meters_per_second = float(data.get("meters_per_second", DEFAULT_WHEEL_CONFIG.meters_per_second))
        degrees_per_second = float(data.get("degrees_per_second", DEFAULT_WHEEL_CONFIG.degrees_per_second))
        wheels: List[WheelSpec] = []
        for entry in data.get("wheels", []):
            if isinstance(entry, Mapping):
                spec = WheelSpec.from_mapping(entry)
                if spec:
                    wheels.append(spec)
        return cls(
            speed=speed,
            meters_per_second=meters_per_second,
            degrees_per_second=degrees_per_second,
            wheels=tuple(wheels),
        )


DEFAULT_WHEEL_CONFIG = WheelConfig(
    speed=1000,
    meters_per_second=0.25,
    degrees_per_second=60.0,
    wheels=(
        WheelSpec(
            id=7,
            role="both",
            calibration=WheelCalibration(up=1, down=-1, left=-1, right=1),
        ),
        WheelSpec(
            id=8,
            role="steer",
            calibration=WheelCalibration(up=0, down=0, left=-1, right=1),
        ),
        WheelSpec(
            id=9,
            role="both",
            calibration=WheelCalibration(up=-1, down=1, left=-1, right=1),
        ),
    ),
)


def build_wheel_config(
    *,
    speed: Optional[int] = None,
    meters_per_second: Optional[float] = None,
    degrees_per_second: Optional[float] = None,
    wheels: Optional[Sequence[Mapping[str, object]]] = None,
) -> WheelConfig:
    """Helper to create a ``WheelConfig`` from simple primitives."""

    base = DEFAULT_WHEEL_CONFIG
    resolved_speed = base.speed if speed is None else int(speed)
    resolved_mps = base.meters_per_second if meters_per_second is None else float(meters_per_second)
    resolved_dps = base.degrees_per_second if degrees_per_second is None else float(degrees_per_second)

    if wheels is None:
        resolved_wheels = base.wheels
    else:
        collected: List[WheelSpec] = []
        for entry in wheels:
            spec = WheelSpec.from_mapping(entry)
            if spec:
                collected.append(spec)
        resolved_wheels = tuple(collected)

    return WheelConfig(
        speed=resolved_speed,
        meters_per_second=resolved_mps,
        degrees_per_second=resolved_dps,
        wheels=resolved_wheels,
    )


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class XLeRobotWheels:
    def __init__(
        self,
        sdk: ScsServoSDK,
        wheel_cfg: Optional[Union[WheelConfig, Mapping[str, object]]] = None,
    ):
        self.sdk = sdk
        if wheel_cfg is None:
            self.config = DEFAULT_WHEEL_CONFIG
        elif isinstance(wheel_cfg, WheelConfig):
            self.config = wheel_cfg
        elif isinstance(wheel_cfg, Mapping):
            self.config = WheelConfig.from_mapping(wheel_cfg)
        else:
            raise TypeError("wheel_cfg must be a WheelConfig or mapping")
        if not self.config.wheels:
            raise ValueError("Wheel configuration must define at least one wheel.")
        self.linear_mps = max(1e-6, float(self.config.meters_per_second))
        self.angular_dps = max(1e-6, float(self.config.degrees_per_second))

    def _apply_action(self, action: str) -> Dict[int, int]:
        payload = {wheel.id: wheel.speed_for(action, self.config.speed) for wheel in self.config.wheels}
        if payload:
            self.sdk.sync_write_wheel_speeds(payload)
        return payload

    def _stop_all(self) -> Dict[int, int]:
        payload = {wheel.id: 0 for wheel in self.config.wheels}
        if payload:
            self.sdk.sync_write_wheel_speeds(payload)
        return payload

    def _run_for(self, action: str, duration_s: float) -> Dict[int, int]:
        duration = max(0.0, float(duration_s))
        payload = self._apply_action(action)
        if payload:
            if duration > 0.0:
                time.sleep(duration)
            self._stop_all()
        return payload

    def _distance_to_duration(self, distance_m: float) -> float:
        return abs(float(distance_m)) / self.linear_mps

    def _angle_to_duration(self, degrees: float) -> float:
        return abs(float(degrees)) / self.angular_dps

    def go_forward(self, meters: float) -> Dict[int, int]:
        """Drive forward for the requested distance in meters."""

        distance = float(meters)
        if distance < 0:
            return self.go_backward(-distance)
        if distance == 0:
            return {}
        return self._run_for("Up", self._distance_to_duration(distance))

    def go_backward(self, meters: float) -> Dict[int, int]:
        """Drive backward for the requested distance in meters."""

        distance = float(meters)
        if distance < 0:
            return self.go_forward(-distance)
        if distance == 0:
            return {}
        return self._run_for("Down", self._distance_to_duration(distance))

    def turn_left(self, degrees: float) -> Dict[int, int]:
        """Turn left by the requested angle in degrees."""

        angle = float(degrees)
        if angle < 0:
            return self.turn_right(-angle)
        if angle == 0:
            return {}
        return self._run_for("Left", self._angle_to_duration(angle))

    def turn_right(self, degrees: float) -> Dict[int, int]:
        """Turn right by the requested angle in degrees."""

        angle = float(degrees)
        if angle < 0:
            return self.turn_left(-angle)
        if angle == 0:
            return {}
        return self._run_for("Right", self._angle_to_duration(angle))

    def apply_wheel_modes(self) -> List[int]:
        """Switch all configured motors to wheel mode."""

        applied: List[int] = []
        for wheel in self.config.wheels:
            self.sdk.set_wheel_mode(wheel.id)
            applied.append(wheel.id)
        return applied

    @staticmethod
    def connect_serial(
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        protocol_end: int = 0,
    ) -> ScsServoSDK:
        """Create and connect an ``ScsServoSDK`` instance."""

        sdk = ScsServoSDK()
        if not sdk.connect(port, baudrate, protocol_end):
            raise RuntimeError(f"Failed to open serial port {port} @ {baudrate}")
        return sdk


