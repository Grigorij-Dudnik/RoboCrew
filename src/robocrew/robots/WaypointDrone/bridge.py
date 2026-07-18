"""Small ROS2 JSON bridge for a waypoint-controlled drone."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


COMMAND_TOPIC = "/drone/waypoint_command"
OBSERVATION_TOPIC = "/drone/observation"


@dataclass
class DroneObservation:
    front_image_b64: str = ""
    map_image_b64: str = ""
    map_span_m: float = 300.0
    gps: dict[str, float] = field(default_factory=dict)
    height_m: float = 0.0
    yaw_rad: float = 0.0
    route_id: str | None = None
    route_state: str = "idle"

    @classmethod
    def from_payload(cls, observation_payload: dict[str, Any]) -> "DroneObservation":
        return cls(
            front_image_b64=observation_payload["front_image_b64"],
            map_image_b64=observation_payload["map_image_b64"],
            map_span_m=observation_payload.get("map_span_m", 300.0),
            gps=observation_payload["gps"],
            height_m=observation_payload["height_m"],
            yaw_rad=observation_payload.get("yaw_rad", 0.0),
            route_id=observation_payload.get("route_id"),
            route_state=observation_payload.get("route_state", "idle"),
        )


class DroneRosBridge:
    """Publish waypoint commands and keep the latest drone observation."""

    def __init__(self):
        self.latest_observation = DroneObservation()
        self._has_observation = False
        self.navigation_mode = "normal"
        self._reuse_latest_observation = False
        self.current_route_id = None
        self.route_active = False
        self._observation_sequence = 0
        self._last_consumed_observation_sequence = 0
        self._observation_changed = threading.Condition()
        self._start_ros()
        if hasattr(self._rclpy, "spin_once"):
            threading.Thread(target=self._spin, daemon=True).start()

    def _spin(self) -> None:
        while self._rclpy.ok():
            self._rclpy.spin_once(self._node, timeout_sec=0.1)

    def _start_ros(self) -> None:
        import rclpy
        from std_msgs.msg import String

        if not rclpy.ok():
            rclpy.init()
        self._rclpy = rclpy
        self._string_msg = String
        self._node = rclpy.create_node("robocrew_drone_bridge")
        self._command_pub = self._node.create_publisher(String, COMMAND_TOPIC, 10)
        self._node.create_subscription(String, OBSERVATION_TOPIC, self._handle_observation, 10)

    def _handle_observation(self, message) -> None:
        flight_observation = DroneObservation.from_payload(json.loads(message.data))
        current_route_id = getattr(self, "current_route_id", None)
        if current_route_id and flight_observation.route_id != current_route_id:
            return
        observation_changed = getattr(self, "_observation_changed", None)
        if observation_changed:
            with observation_changed:
                self.latest_observation = flight_observation
                if flight_observation.route_id == current_route_id:
                    self.route_active = flight_observation.route_state == "executing"
                self._observation_sequence += 1
                self._has_observation = True
                observation_changed.notify_all()
        else:
            self.latest_observation = flight_observation
            self.route_active = flight_observation.route_state == "executing"
            self._has_observation = True

    def get_observation(self) -> DroneObservation:
        if hasattr(self, "_observation_changed"):
            with self._observation_changed:
                if self._reuse_latest_observation:
                    self._reuse_latest_observation = False
                    return self.latest_observation
                self._observation_changed.wait_for(
                    lambda: self._observation_sequence > self._last_consumed_observation_sequence
                )
                self._last_consumed_observation_sequence = self._observation_sequence
                return self.latest_observation
        while not self._has_observation:
            self._rclpy.spin_once(self._node, timeout_sec=0.1)
        flight_observation = self.latest_observation
        self._has_observation = False
        return flight_observation

    @property
    def observation_sequence(self) -> int:
        return self._observation_sequence

    def wait_for_observation(self, after_sequence: int) -> tuple[DroneObservation, int]:
        with self._observation_changed:
            self._observation_changed.wait_for(
                lambda: self._observation_sequence > after_sequence or not self.route_active
            )
            return self.latest_observation, self._observation_sequence

    def wait_for_route_end(self, route_id: str) -> DroneObservation:
        with self._observation_changed:
            self._observation_changed.wait_for(
                lambda: self.current_route_id != route_id or not self.route_active
            )
            return self.latest_observation

    def set_waypoints(
        self,
        route_waypoints: list[dict[str, Any]],
        altitude_m: float | None = None,
        strategy: str | None = None,
    ) -> dict[str, Any]:
        self._reuse_latest_observation = False
        self.current_route_id = uuid.uuid4().hex
        self.route_active = True
        command_message = self._string_msg()
        command_message.data = json.dumps({
            "command": "set_waypoints",
            "route_id": self.current_route_id,
            "waypoints": route_waypoints,
            "altitude_m": altitude_m,
            "strategy": strategy,
        })
        self._command_pub.publish(command_message)
        return {
            "status": "submitted",
            "route_id": self.current_route_id,
            "current_gps": self.latest_observation.gps,
        }

    def move_forward(self, distance_meters: float) -> dict[str, Any]:
        return self._submit_relative_motion(
            "move_forward",
            distance_meters=float(distance_meters),
        )

    def turn_left(self, angle_degrees: float) -> dict[str, Any]:
        return self._submit_relative_motion(
            "turn_left",
            angle_degrees=float(angle_degrees),
        )

    def turn_right(self, angle_degrees: float) -> dict[str, Any]:
        return self._submit_relative_motion(
            "turn_right",
            angle_degrees=float(angle_degrees),
        )

    def _submit_relative_motion(self, motion: str, **motion_arguments) -> dict[str, Any]:
        self._reuse_latest_observation = False
        self.current_route_id = uuid.uuid4().hex
        self.route_active = True
        command_message = self._string_msg()
        command_message.data = json.dumps({
            "command": "relative_motion",
            "route_id": self.current_route_id,
            "motion": motion,
            **motion_arguments,
        })
        self._command_pub.publish(command_message)
        return {
            "status": "submitted",
            "route_id": self.current_route_id,
            "current_gps": self.latest_observation.gps,
        }

    def set_navigation_mode(self, navigation_mode: str) -> None:
        self.navigation_mode = navigation_mode
        self._reuse_latest_observation = True

    def stop_route(self, reason: str) -> None:
        command_message = self._string_msg()
        command_message.data = json.dumps({
            "command": "stop_route",
            "route_id": self.current_route_id,
            "reason": reason,
        })
        self._command_pub.publish(command_message)
