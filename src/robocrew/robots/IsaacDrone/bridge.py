"""Small ROS2 JSON bridge for the Isaac Sim drone prototype."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


COMMAND_TOPIC = "/isaac_drone/waypoint_command"
OBSERVATION_TOPIC = "/isaac_drone/observation"


@dataclass
class IsaacDroneObservation:
    front_image_b64: str = ""
    map_image_b64: str = ""
    gps: dict[str, float] = field(default_factory=dict)
    height_m: float = 0.0

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "IsaacDroneObservation":
        return cls(
            front_image_b64=payload["front_image_b64"],
            map_image_b64=payload["map_image_b64"],
            gps=payload["gps"],
            height_m=payload["height_m"],
        )


class IsaacDroneRosBridge:
    """Publish waypoint commands and keep the latest simulator observation."""

    def __init__(self):
        self.latest_observation = IsaacDroneObservation()
        self._start_ros()

    def _start_ros(self) -> None:
        import rclpy
        from std_msgs.msg import String

        if not rclpy.ok():
            rclpy.init()
        self._rclpy = rclpy
        self._string_msg = String
        self._node = rclpy.create_node("robocrew_isaac_drone_bridge")
        self._command_pub = self._node.create_publisher(String, COMMAND_TOPIC, 10)
        self._node.create_subscription(String, OBSERVATION_TOPIC, self._handle_observation, 10)

    def _handle_observation(self, msg) -> None:
        self.latest_observation = IsaacDroneObservation.from_payload(json.loads(msg.data))

    def get_observation(self) -> IsaacDroneObservation:
        self._rclpy.spin_once(self._node, timeout_sec=0.0)
        return self.latest_observation

    def set_waypoints(
        self,
        waypoints: list[dict[str, Any]],
        altitude_m: float | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        msg = self._string_msg()
        msg.data = json.dumps({
            "waypoints": waypoints,
            "altitude_m": altitude_m,
            "note": note,
        })
        self._command_pub.publish(msg)
        return {
            "status": "submitted",
            "current_gps": self.latest_observation.gps,
        }
