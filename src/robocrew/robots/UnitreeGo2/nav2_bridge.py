"""ROS 2 bridge for Unitree Go2 waypoint navigation."""

from __future__ import annotations

import base64
import math
import threading
from dataclasses import dataclass, field
from queue import Queue
from typing import Any

import cv2
import numpy as np
import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_msgs.action import FollowWaypoints
from nav_msgs.msg import OccupancyGrid, Path
from rclpy.action import ActionClient
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    HistoryPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import CompressedImage

from robocrew.robots.WaypointDrone.map_utils import draw_normalized_grid_on_map


@dataclass(frozen=True)
class MapMetadata:
    width: int
    height: int
    resolution: float
    origin_x: float
    origin_y: float
    origin_yaw: float


@dataclass(frozen=True)
class MapPose:
    x: float
    y: float
    yaw: float = 0.0


@dataclass(frozen=True)
class NavigationEvent:
    kind: str
    current_waypoint: int | None = None
    waypoint_count: int | None = None
    detail: str = ""


@dataclass(frozen=True)
class Go2Observation:
    camera_image_b64: str = ""
    map_image_b64: str = ""
    navigation_state: str = "idle"
    current_waypoint: int = 0
    waypoint_count: int = 0


@dataclass
class _BridgeState:
    map_cells: np.ndarray | None = None
    map_metadata: MapMetadata | None = None
    camera_image_b64: str = ""
    robot_pose: MapPose | None = None
    travelled_path: list[MapPose] = field(default_factory=list)
    global_plan: list[MapPose] = field(default_factory=list)
    submitted_waypoints: list[MapPose] = field(default_factory=list)
    current_waypoint: int = 0
    navigation_state: str = "idle"


def _yaw_from_quaternion(quaternion) -> float:
    sin_yaw = 2.0 * (
        quaternion.w * quaternion.z + quaternion.x * quaternion.y
    )
    cos_yaw = 1.0 - 2.0 * (
        quaternion.y * quaternion.y + quaternion.z * quaternion.z
    )
    return math.atan2(sin_yaw, cos_yaw)


class UnitreeGo2NavBridge:
    """Own the ROS node, current observation, and active FollowWaypoints goal."""

    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue
        self._state = _BridgeState()
        self._state_lock = threading.RLock()
        self._goal_handle = None

        if not rclpy.ok():
            rclpy.init(args=None)
        self.node = Node("robocrew_unitree_go2")
        self.executor = SingleThreadedExecutor()
        self.executor.add_node(self.node)

        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        camera_qos = QoSProfile(
            depth=1,
            history=HistoryPolicy.KEEP_LAST,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.node.create_subscription(
            CompressedImage,
            "/camera/rgb_compressed",
            self._on_camera,
            camera_qos,
        )
        self.node.create_subscription(
            OccupancyGrid, "/map", self._on_map, map_qos
        )
        self.node.create_subscription(
            PoseWithCovarianceStamped, "/pose", self._on_pose, 10
        )
        self.node.create_subscription(Path, "/plan", self._on_plan, 10)
        self._waypoint_client = ActionClient(
            self.node, FollowWaypoints, "follow_waypoints"
        )

        self._spin_thread = threading.Thread(
            target=self.executor.spin,
            name="go2-ros-executor",
            daemon=True,
        )
        self._spin_thread.start()

    @property
    def navigation_active(self) -> bool:
        with self._state_lock:
            return self._state.navigation_state in {"submitting", "active", "cancelling"}

    def normalized_waypoints_to_map(
        self, waypoints: list[dict[str, Any]]
    ) -> list[MapPose]:
        with self._state_lock:
            metadata = self._state.map_metadata
            robot_pose = self._state.robot_pose
        if metadata is None:
            raise RuntimeError("Nav2 map is not available")

        poses = []
        for index, waypoint in enumerate(waypoints):
            normalized_x = float(waypoint["x"])
            normalized_y = float(waypoint["y"])
            if not 0.0 <= normalized_x <= 1.0 or not 0.0 <= normalized_y <= 1.0:
                raise ValueError("waypoint x and y must be between 0 and 1")
            pixel_x = normalized_x * (metadata.width - 1)
            pixel_y = normalized_y * (metadata.height - 1)
            world_x, world_y = self._image_to_world(
                pixel_x, pixel_y, metadata
            )
            yaw = waypoint.get("yaw")
            poses.append(
                MapPose(
                    world_x,
                    world_y,
                    float(yaw) if yaw is not None else math.nan,
                )
            )

        for index, pose in enumerate(poses):
            if not math.isnan(pose.yaw):
                continue
            if index + 1 < len(poses):
                next_pose = poses[index + 1]
                yaw = math.atan2(next_pose.y - pose.y, next_pose.x - pose.x)
            elif index > 0:
                previous_pose = poses[index - 1]
                yaw = math.atan2(
                    pose.y - previous_pose.y,
                    pose.x - previous_pose.x,
                )
            elif robot_pose is not None:
                yaw = robot_pose.yaw
            else:
                raise RuntimeError(
                    "robot pose is unavailable; provide waypoint yaw"
                )
            poses[index] = MapPose(pose.x, pose.y, yaw)
        return poses

    def submit_waypoints(
        self,
        waypoints: list[MapPose],
        *,
        travelled_path: list[MapPose] | None = None,
    ) -> None:
        if not waypoints:
            raise ValueError("waypoints must contain at least one waypoint")
        if self.navigation_active:
            raise RuntimeError("a Nav2 waypoint goal is already active")
        if not self._waypoint_client.wait_for_server(timeout_sec=2.0):
            raise RuntimeError("follow_waypoints action server is not available")

        goal = FollowWaypoints.Goal()
        now = self.node.get_clock().now().to_msg()
        for waypoint in waypoints:
            pose = PoseStamped()
            pose.header.frame_id = "map"
            pose.header.stamp = now
            pose.pose.position.x = waypoint.x
            pose.pose.position.y = waypoint.y
            pose.pose.orientation.z = math.sin(waypoint.yaw / 2.0)
            pose.pose.orientation.w = math.cos(waypoint.yaw / 2.0)
            goal.poses.append(pose)

        with self._state_lock:
            self._state.submitted_waypoints = list(waypoints)
            self._state.global_plan.clear()
            self._state.travelled_path = list(travelled_path or [])
            self._state.current_waypoint = 0
            self._state.navigation_state = "submitting"
            if (
                self._state.robot_pose
                and self._should_record_pose(self._state.robot_pose)
            ):
                self._state.travelled_path.append(self._state.robot_pose)

        goal_future = self._waypoint_client.send_goal_async(
            goal, feedback_callback=self._on_waypoint_feedback
        )
        goal_future.add_done_callback(self._on_goal_response)

    def cancel_navigation(self) -> bool:
        with self._state_lock:
            if self._state.navigation_state != "active":
                return False
            goal_handle = self._goal_handle
            self._state.navigation_state = "cancelling"
        cancel_future = goal_handle.cancel_goal_async()
        cancel_future.add_done_callback(self._on_cancel_response)
        return True

    def get_observation(self) -> Go2Observation:
        with self._state_lock:
            map_image_b64 = self._render_map_locked()
            return Go2Observation(
                camera_image_b64=self._state.camera_image_b64,
                map_image_b64=map_image_b64,
                navigation_state=self._state.navigation_state,
                current_waypoint=self._state.current_waypoint,
                waypoint_count=len(self._state.submitted_waypoints),
            )

    def remaining_waypoints(self) -> list[MapPose]:
        with self._state_lock:
            return list(
                self._state.submitted_waypoints[self._state.current_waypoint :]
            )

    def travelled_path(self) -> list[MapPose]:
        with self._state_lock:
            return list(self._state.travelled_path)

    def close(self) -> None:
        self.executor.shutdown()
        self._spin_thread.join(timeout=2.0)
        self.executor.remove_node(self.node)
        self.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    def _on_camera(self, message: CompressedImage) -> None:
        with self._state_lock:
            self._state.camera_image_b64 = base64.b64encode(
                bytes(message.data)
            ).decode("ascii")

    def _on_map(self, message: OccupancyGrid) -> None:
        width = int(message.info.width)
        height = int(message.info.height)
        if width <= 0 or height <= 0 or len(message.data) != width * height:
            return
        metadata = MapMetadata(
            width=width,
            height=height,
            resolution=float(message.info.resolution),
            origin_x=float(message.info.origin.position.x),
            origin_y=float(message.info.origin.position.y),
            origin_yaw=_yaw_from_quaternion(message.info.origin.orientation),
        )
        cells = np.asarray(message.data, dtype=np.int8).reshape(height, width)
        with self._state_lock:
            self._state.map_metadata = metadata
            self._state.map_cells = cells.copy()

    def _on_pose(self, message: PoseWithCovarianceStamped) -> None:
        pose_message = message.pose.pose
        pose = MapPose(
            x=float(pose_message.position.x),
            y=float(pose_message.position.y),
            yaw=_yaw_from_quaternion(pose_message.orientation),
        )
        with self._state_lock:
            self._state.robot_pose = pose
            if self.navigation_active and self._should_record_pose(pose):
                self._state.travelled_path.append(pose)

    def _on_plan(self, message: Path) -> None:
        plan = [
            MapPose(
                x=float(pose.pose.position.x),
                y=float(pose.pose.position.y),
                yaw=_yaw_from_quaternion(pose.pose.orientation),
            )
            for pose in message.poses
        ]
        with self._state_lock:
            if self.navigation_active:
                self._state.global_plan = plan

    # ROS future failures happen on the executor thread. Convert them to
    # navigation events so the agent does not wait forever for a dead goal.
    def _on_goal_response(self, future) -> None:
        try:
            goal_handle = future.result()
        except Exception as exc:
            self._finish_navigation("failed", detail=str(exc))
            return
        if not goal_handle.accepted:
            self._finish_navigation("failed", detail="goal rejected")
            return

        with self._state_lock:
            self._goal_handle = goal_handle
            self._state.navigation_state = "active"
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self._on_navigation_result)

    def _on_waypoint_feedback(self, feedback_message) -> None:
        current_waypoint = int(feedback_message.feedback.current_waypoint)
        with self._state_lock:
            if current_waypoint == self._state.current_waypoint:
                return
            self._state.current_waypoint = current_waypoint

    def _on_navigation_result(self, future) -> None:
        try:
            wrapped_result = future.result()
            status = int(wrapped_result.status)
            missed = list(wrapped_result.result.missed_waypoints)
        except Exception as exc:
            self._finish_navigation("failed", detail=str(exc))
            return

        if status == GoalStatus.STATUS_SUCCEEDED and not missed:
            state = "completed"
            detail = ""
        elif status == GoalStatus.STATUS_CANCELED:
            state = "cancelled"
            detail = ""
        else:
            state = "failed"
            detail = f"status={status}, missed_waypoints={missed}"
        self._finish_navigation(state, detail=detail)

    def _on_cancel_response(self, future) -> None:
        try:
            response = future.result()
            if not response.goals_canceling:
                with self._state_lock:
                    self._state.navigation_state = "active"
                self._emit_navigation_event(
                    NavigationEvent(
                        "failed",
                        detail="Nav2 rejected cancellation",
                    )
                )
        except Exception as exc:
            with self._state_lock:
                self._state.navigation_state = "active"
            self._emit_navigation_event(
                NavigationEvent(
                    "failed",
                    detail=f"cancellation failed: {exc}",
                )
            )

    def _finish_navigation(self, state: str, *, detail: str = "") -> None:
        with self._state_lock:
            self._state.navigation_state = state
            waypoint_count = len(self._state.submitted_waypoints)
            if state == "completed":
                self._state.current_waypoint = waypoint_count
            current_waypoint = self._state.current_waypoint
            self._goal_handle = None
            if self._state.robot_pose and self._should_record_pose(
                self._state.robot_pose
            ):
                self._state.travelled_path.append(self._state.robot_pose)
            if state == "completed":
                self._state.global_plan.clear()
        self._emit_navigation_event(
            NavigationEvent(
                state,
                current_waypoint=current_waypoint,
                waypoint_count=waypoint_count,
                detail=detail,
            )
        )

    def _emit_navigation_event(self, event: NavigationEvent) -> None:
        self.event_queue.put(event)

    def _should_record_pose(self, pose: MapPose) -> bool:
        if not self._state.travelled_path:
            return True
        previous = self._state.travelled_path[-1]
        return math.hypot(pose.x - previous.x, pose.y - previous.y) >= 0.05

    def _render_map_locked(self) -> str:
        cells = self._state.map_cells
        metadata = self._state.map_metadata
        if cells is None or metadata is None:
            return ""

        image = np.full(cells.shape, 205, dtype=np.uint8)
        image[cells == 0] = 254
        image[cells >= 65] = 0
        uncertain = (cells > 0) & (cells < 65)
        image[uncertain] = 254 - (cells[uncertain].astype(np.int16) * 254 // 100)
        image = np.flipud(image)
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        self._draw_path(image, self._state.travelled_path, metadata, (0, 0, 255))
        planned_path = (
            self._state.global_plan
            if self._state.global_plan
            else self._state.submitted_waypoints[self._state.current_waypoint :]
        )
        if planned_path and self._state.robot_pose:
            planned_path = [self._state.robot_pose, *planned_path]
        self._draw_path(image, planned_path, metadata, (255, 0, 0))
        self._draw_waypoints(image, metadata)
        self._draw_robot(image, metadata)

        encoded, jpeg = cv2.imencode(".jpg", image)
        if not encoded:
            raise RuntimeError("failed to encode Nav2 map as JPEG")
        map_image_b64 = base64.b64encode(jpeg).decode("ascii")
        return draw_normalized_grid_on_map(map_image_b64, grid_color=(96, 96, 96))

    def _draw_path(
        self,
        image: np.ndarray,
        path: list[MapPose],
        metadata: MapMetadata,
        color: tuple[int, int, int],
    ) -> None:
        if len(path) < 2:
            return
        points = np.asarray(
            [self._world_to_image(pose.x, pose.y, metadata) for pose in path],
            dtype=np.int32,
        )
        cv2.polylines(image, [points], False, color, 3, cv2.LINE_AA)

    def _draw_waypoints(
        self, image: np.ndarray, metadata: MapMetadata
    ) -> None:
        remaining = self._state.submitted_waypoints[
            self._state.current_waypoint :
        ]
        for index, waypoint in enumerate(
            remaining, start=self._state.current_waypoint + 1
        ):
            point = self._world_to_image(waypoint.x, waypoint.y, metadata)
            cv2.circle(image, point, 6, (255, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(
                image,
                str(index),
                (point[0] + 7, point[1] - 7),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 0, 0),
                2,
                cv2.LINE_AA,
            )

    def _draw_robot(
        self, image: np.ndarray, metadata: MapMetadata
    ) -> None:
        pose = self._state.robot_pose
        if pose is None:
            return
        center = self._world_to_image(pose.x, pose.y, metadata)
        image_angle = metadata.origin_yaw - pose.yaw
        length = max(20, min(image.shape[:2]) // 25)
        tip = (
            int(round(center[0] + length * math.cos(image_angle))),
            int(round(center[1] + length * math.sin(image_angle))),
        )
        cv2.circle(image, center, 9, (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(image, center, 7, (0, 255, 255), -1, cv2.LINE_AA)
        cv2.arrowedLine(image, center, tip, (0, 0, 0), 7, cv2.LINE_AA, tipLength=0.35)
        cv2.arrowedLine(
            image, center, tip, (0, 255, 255), 4, cv2.LINE_AA, tipLength=0.35
        )

    @staticmethod
    def _image_to_world(
        pixel_x: float, pixel_y: float, metadata: MapMetadata
    ) -> tuple[float, float]:
        local_x = pixel_x * metadata.resolution
        local_y = (metadata.height - 1 - pixel_y) * metadata.resolution
        cos_origin = math.cos(metadata.origin_yaw)
        sin_origin = math.sin(metadata.origin_yaw)
        return (
            metadata.origin_x + local_x * cos_origin - local_y * sin_origin,
            metadata.origin_y + local_x * sin_origin + local_y * cos_origin,
        )

    @staticmethod
    def _world_to_image(
        world_x: float, world_y: float, metadata: MapMetadata
    ) -> tuple[int, int]:
        delta_x = world_x - metadata.origin_x
        delta_y = world_y - metadata.origin_y
        cos_origin = math.cos(metadata.origin_yaw)
        sin_origin = math.sin(metadata.origin_yaw)
        local_x = delta_x * cos_origin + delta_y * sin_origin
        local_y = -delta_x * sin_origin + delta_y * cos_origin
        return (
            int(round(local_x / metadata.resolution)),
            int(round(metadata.height - 1 - local_y / metadata.resolution)),
        )
