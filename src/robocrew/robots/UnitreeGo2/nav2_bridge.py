"""ROS 2 bridge for Unitree Go2 waypoint navigation."""

from __future__ import annotations

import base64
import math
import threading
from dataclasses import dataclass, field
from queue import Queue
from typing import Any

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

from robocrew.robots.UnitreeGo2.map_renderer import Go2MapRenderer


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

    def __init__(
        self,
        event_queue: Queue,
        *,
        maps_dir: str | None = None,
        current_map_file: str | None = None,
    ):
        self.event_queue = event_queue
        self._state = _BridgeState()
        self._state_lock = threading.RLock()
        self._goal_handle = None
        self._map_renderer = Go2MapRenderer(maps_dir, current_map_file)

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
            PoseWithCovarianceStamped, "/amcl_pose", self._on_pose, 10
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
            return self._state.navigation_state in {
                "submitting",
                "active",
                "cancelling",
            }

    def submit_waypoints(
        self,
        waypoints: list[dict[str, Any]],
        *,
        travelled_path: list[dict[str, float]] | None = None,
    ) -> None:
        if not waypoints:
            raise ValueError("waypoints must contain at least one waypoint")
        if self.navigation_active:
            raise RuntimeError("a Nav2 waypoint goal is already active")
        with self._state_lock:
            metadata = self._state.map_metadata
            robot_pose = self._state.robot_pose
        if metadata is None:
            raise RuntimeError("Nav2 map is not available")

        map_waypoints = []
        for waypoint in waypoints:
            normalized_x = float(waypoint["x"])
            normalized_y = float(waypoint["y"])
            if not 0.0 <= normalized_x <= 1.0 or not 0.0 <= normalized_y <= 1.0:
                raise ValueError("waypoint x and y must be between 0 and 1")
            pixel_x = normalized_x * (metadata.width - 1)
            pixel_y = normalized_y * (metadata.height - 1)
            world_x, world_y = self._map_renderer.image_to_world(
                pixel_x, pixel_y, metadata
            )
            yaw = waypoint.get("yaw")
            map_waypoints.append(
                MapPose(
                    world_x,
                    world_y,
                    float(yaw) if yaw is not None else math.nan,
                )
            )

        for index, pose in enumerate(map_waypoints):
            if not math.isnan(pose.yaw):
                continue
            if index + 1 < len(map_waypoints):
                next_pose = map_waypoints[index + 1]
                yaw = math.atan2(next_pose.y - pose.y, next_pose.x - pose.x)
            elif index > 0:
                previous_pose = map_waypoints[index - 1]
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
            map_waypoints[index] = MapPose(pose.x, pose.y, yaw)
        if not self._waypoint_client.wait_for_server(timeout_sec=2.0):
            raise RuntimeError("follow_waypoints action server is not available")

        goal = FollowWaypoints.Goal()
        now = self.node.get_clock().now().to_msg()
        for waypoint in map_waypoints:
            pose = PoseStamped()
            pose.header.frame_id = "map"
            pose.header.stamp = now
            pose.pose.position.x = waypoint.x
            pose.pose.position.y = waypoint.y
            pose.pose.orientation.z = math.sin(waypoint.yaw / 2.0)
            pose.pose.orientation.w = math.cos(waypoint.yaw / 2.0)
            goal.poses.append(pose)

        with self._state_lock:
            self._state.submitted_waypoints = map_waypoints
            self._state.global_plan.clear()
            self._state.travelled_path = [
                MapPose(**pose) for pose in travelled_path or []
            ]
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
            camera_image = self._state.camera_image_b64
            map_cells = self._state.map_cells
            map_metadata = self._state.map_metadata
            travelled_path = list(self._state.travelled_path)
            global_plan = list(self._state.global_plan)
            waypoints = list(self._state.submitted_waypoints)
            current_waypoint = self._state.current_waypoint
            robot_pose = self._state.robot_pose
            navigation_state = self._state.navigation_state
        map_image = self._map_renderer.render(
            map_cells,
            map_metadata,
            travelled_path,
            global_plan,
            waypoints,
            current_waypoint,
            robot_pose,
        )
        return Go2Observation(
            camera_image_b64=camera_image,
            map_image_b64=map_image,
            navigation_state=navigation_state,
            current_waypoint=current_waypoint,
            waypoint_count=len(waypoints),
        )

    def route_progress(self) -> tuple[int, list[MapPose]]:
        with self._state_lock:
            state = self._state
            remaining = len(state.submitted_waypoints) - state.current_waypoint
            return remaining, list(state.travelled_path)

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
                self.event_queue.put(
                    NavigationEvent(
                        "failed",
                        detail="Nav2 rejected cancellation",
                    )
                )
        except Exception as exc:
            with self._state_lock:
                self._state.navigation_state = "active"
            self.event_queue.put(
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
        self.event_queue.put(
            NavigationEvent(
                state,
                current_waypoint=current_waypoint,
                waypoint_count=waypoint_count,
                detail=detail,
            )
        )

    def _should_record_pose(self, pose: MapPose) -> bool:
        if not self._state.travelled_path:
            return True
        previous = self._state.travelled_path[-1]
        return math.hypot(pose.x - previous.x, pose.y - previous.y) >= 0.05
