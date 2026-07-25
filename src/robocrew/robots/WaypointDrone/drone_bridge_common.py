"""State shared by simulation and real-drone connectors."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class DroneObservation:
    front_image_b64: str = ""
    down_image_b64: str = ""
    map_image_b64: str = ""
    map_span_m: float = 300.0
    gps: dict[str, float] = field(default_factory=dict)
    height_m: float = 0.0
    yaw_rad: float = 0.0
    route_state: str = "idle"


class DroneBridge:
    def __init__(self):
        self.latest_observation = DroneObservation()
        self.navigation_mode = "normal"
        self._reuse_latest_observation = False
        self.route_active = False
        self._observation_number = 0
        self._last_consumed_observation_number = 0
        self._observation_changed = threading.Condition()

    def _start_command(self) -> None:
        self._reuse_latest_observation = False
        self.route_active = True

    def _store_observation(self, observation: DroneObservation) -> None:
        with self._observation_changed:
            self.latest_observation = observation
            self.route_active = observation.route_state == "executing"
            self._observation_number += 1
            self._observation_changed.notify_all()

    def get_observation(self) -> DroneObservation:
        with self._observation_changed:
            if self._reuse_latest_observation:
                self._reuse_latest_observation = False
                return self.latest_observation
            self._observation_changed.wait_for(
                lambda: self._observation_number
                > self._last_consumed_observation_number
            )
            self._last_consumed_observation_number = self._observation_number
            return self.latest_observation

    @property
    def observation_number(self) -> int:
        return self._observation_number

    def wait_for_observation(self, after_observation_number: int) -> tuple[DroneObservation, int]:
        with self._observation_changed:
            self._observation_changed.wait_for(
                lambda: self._observation_number > after_observation_number
                or not self.route_active
            )
            return self.latest_observation, self._observation_number

    def wait_for_route_end(self) -> DroneObservation:
        with self._observation_changed:
            self._observation_changed.wait_for(lambda: not self.route_active)
            return self.latest_observation

    def set_navigation_mode(self, navigation_mode: str) -> None:
        self.navigation_mode = navigation_mode
        self._reuse_latest_observation = True
