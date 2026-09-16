"""Small ROS2 JSON bridge for a waypoint-controlled drone."""

from __future__ import annotations

import base64
import json
import threading
from typing import Any

from robocrew.robots.WaypointDrone.drone_bridge_common import DroneBridge, DroneObservation


COMMAND_TOPIC = "/drone/waypoint_command"
OBSERVATION_TOPIC = "/drone/observation"
FRONT_IMAGE_TOPIC = "/drone/camera/front/compressed"
DOWN_IMAGE_TOPIC = "/drone/camera/down/compressed"
MAP_IMAGE_TOPIC = "/drone/map/compressed"


class IsaacRosBridge(DroneBridge):
    """Connect a WaypointDroneAgent to the Isaac ROS interface."""

    def __init__(self):
        super().__init__()
        self._pending_images: dict[int, dict[str, bytes]] = {}
        self._pending_metadata: dict[int, dict[str, Any]] = {}
        self._start_ros()
        if hasattr(self._rclpy, "spin_once"):
            threading.Thread(target=self._spin, daemon=True).start()

    def _spin(self) -> None:
        while self._rclpy.ok():
            self._rclpy.spin_once(self._node, timeout_sec=0.1)

    def _start_ros(self) -> None:
        import rclpy
        from sensor_msgs.msg import CompressedImage
        from std_msgs.msg import String

        if not rclpy.ok():
            rclpy.init()
        self._rclpy = rclpy
        self._string_msg = String
        self._node = rclpy.create_node("robocrew_drone_bridge")
        self._command_pub = self._node.create_publisher(String, COMMAND_TOPIC, 10)
        self._node.create_subscription(String, OBSERVATION_TOPIC, self._handle_observation, 10)
        for image_name, topic in (
            ("front", FRONT_IMAGE_TOPIC),
            ("down", DOWN_IMAGE_TOPIC),
            ("map", MAP_IMAGE_TOPIC),
        ):
            self._node.create_subscription(
                CompressedImage,
                topic,
                lambda message, name=image_name: self._handle_image(name, message),
                10,
            )

    def _handle_observation(self, message) -> None:
        observation_payload = json.loads(message.data)
        stamp_ns = observation_payload["stamp_ns"]
        self._pending_metadata[stamp_ns] = observation_payload
        self._assemble_observation(stamp_ns)

    def _handle_image(self, image_name: str, message) -> None:
        stamp_ns = message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec
        self._pending_images.setdefault(stamp_ns, {})[image_name] = bytes(message.data)
        self._assemble_observation(stamp_ns)

    def _assemble_observation(self, stamp_ns: int) -> None:
        images = self._pending_images.get(stamp_ns, {})
        if stamp_ns not in self._pending_metadata or len(images) != 3:
            return
        observation_payload = self._pending_metadata.pop(stamp_ns)
        self._pending_images.pop(stamp_ns)
        observation_payload.update({
            "front_image_b64": base64.b64encode(images["front"]).decode(),
            "down_image_b64": base64.b64encode(images["down"]).decode(),
            "map_image_b64": base64.b64encode(images["map"]).decode(),
        })
        self._store_observation(
            DroneObservation(
                front_image_b64=observation_payload["front_image_b64"],
                down_image_b64=observation_payload["down_image_b64"],
                map_image_b64=observation_payload["map_image_b64"],
                map_span_m=observation_payload.get("map_span_m", 300.0),
                gps=observation_payload["gps"],
                height_m=observation_payload["height_m"],
                yaw_rad=observation_payload.get("yaw_rad", 0.0),
                route_state=observation_payload.get("route_state", "idle"),
            )
        )

    def set_waypoints(
        self,
        route_waypoints: list[dict[str, Any]],
        altitude_m: float | None = None,
        strategy: str | None = None,
    ) -> None:
        self._submit_command(
            "set_waypoints",
            waypoints=route_waypoints,
            altitude_m=altitude_m,
            strategy=strategy,
        )

    def land(self) -> None:
        self._submit_command("land")

    def move_forward(self, distance_meters: float) -> None:
        self._submit_relative_motion(
            "move_forward",
            distance_meters=float(distance_meters),
        )

    def turn_left(self, angle_degrees: float) -> None:
        self._submit_relative_motion(
            "turn_left",
            angle_degrees=float(angle_degrees),
        )

    def turn_right(self, angle_degrees: float) -> None:
        self._submit_relative_motion(
            "turn_right",
            angle_degrees=float(angle_degrees),
        )

    def _submit_relative_motion(self, motion: str, **motion_arguments) -> None:
        self._submit_command(
            "relative_motion",
            motion=motion,
            **motion_arguments,
        )

    def _submit_command(self, command: str, **arguments) -> None:
        self._start_command()
        command_message = self._string_msg()
        command_message.data = json.dumps({
            "command": command,
            **arguments,
        })
        self._command_pub.publish(command_message)

    def stop_route(self) -> None:
        command_message = self._string_msg()
        command_message.data = json.dumps({"command": "stop_route"})
        self._command_pub.publish(command_message)
