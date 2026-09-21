"""LangChain tool factories for Unitree Go2 navigation."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from typing_extensions import TypedDict

from robocrew.robots.UnitreeGo2.nav2_bridge import MapPose


class RequiredWaypoint(TypedDict):
    x: float
    y: float


class Waypoint(RequiredWaypoint, total=False):
    yaw: float
    purpose: str


def create_set_waypoints(bridge, mission_state):
    @tool(extras={"silent": True})
    def set_waypoints(
        situation_reassessment: Annotated[
            str,
            "Write this first. Compare the current camera and map with previous "
            "observations and route; summarize what changed and what remains.",
        ],
        strategy: Annotated[
            str,
            "After the reassessment, explain the next route and why.",
        ],
        *,
        waypoints: Annotated[
            list[Waypoint],
            "Trace the route on the CURRENT annotated map. Add a waypoint at "
            "meaningful bends so every segment remains on visible free space. "
            "x and y are normalized from 0 to 1.",
        ],
    ) -> str:
        """Reassess the situation, then start a non-blocking Nav2 route."""
        print(f"Situation reassessment: {situation_reassessment}")
        print(f"Strategy: {strategy}")

        task = mission_state.active_task
        if task is None:
            return "no_active_task"
        map_waypoints = bridge.normalized_waypoints_to_map(waypoints)
        travelled_path = [MapPose(**pose) for pose in task.travelled_path]
        bridge.submit_waypoints(
            map_waypoints, travelled_path=travelled_path
        )
        mission_state.save_task_route(strategy, waypoints)
        return f"navigation_started: waypoint_count={len(map_waypoints)}"

    return set_waypoints


def create_cancel_navigation(bridge, mission_state):
    @tool
    def cancel_navigation(reason: str) -> str:
        """Cancel the active Nav2 route before starting a different route."""
        if not bridge.cancel_navigation():
            return "navigation_not_active"
        remaining_count = len(bridge.remaining_waypoints())
        mission_state.save_route_progress(
            remaining_count, bridge.travelled_path()
        )
        return (
            f"navigation_cancellation_requested: reason={reason}, "
            f"remaining_waypoints={remaining_count}"
        )

    return cancel_navigation
