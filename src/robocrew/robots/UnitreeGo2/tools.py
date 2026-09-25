"""LangChain tool factories for Unitree Go2 navigation."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from typing_extensions import NotRequired, TypedDict


class Waypoint(TypedDict):
    x: float
    y: float
    purpose: str
    yaw: NotRequired[float]


@tool(extras={"requires_navigation": True})
def continue_navigation() -> str:
    """Keep the active Nav2 route running."""
    return "navigation_continues"


def create_plan_tasks(bridge, mission_state):
    @tool
    def plan_tasks(
        tasks: Annotated[
            list[str],
            "All independently completable jobs requested by the user, in order.",
        ],
        interrupt_current: Annotated[
            bool,
            "True only when these tasks must pause and replace the active task.",
        ] = False,
    ) -> str:
        """Plan the complete workload, optionally interrupting the active task."""
        if not tasks:
            return "No tasks planned"
        urgent = mission_state.active_task is not None and interrupt_current
        for task in reversed(tasks) if urgent else tasks:
            mission_state.queue_task(task, run_next=urgent)
        summary = "; ".join(tasks)
        if not urgent:
            return f"Tasks planned: {summary}"

        if bridge.cancel_navigation():
            remaining_count, travelled_path = bridge.route_progress()
            mission_state.save_route_progress(
                remaining_count,
                travelled_path,
            )
            mission_state.request_task_switch_after_cancel()
            return f"Tasks planned; cancelling current route: {summary}"

        mission_state.switch_to_next_task()
        return f"Tasks activated; previous task paused: {summary}"

    return plan_tasks


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
            "Trace the route on the CURRENT annotated map. "
            "x and y are normalized from 0 to 1.",
        ],
    ) -> str:
        """Reassess the situation, then start a non-blocking Nav2 route."""
        task = mission_state.active_task
        if task is None:
            return "no_active_task"
        if bridge.navigation_active:
            return "navigation_already_active"
        bridge.submit_waypoints(
            waypoints, travelled_path=task.travelled_path
        )
        mission_state.save_task_route(strategy, waypoints)
        return f"navigation_started: waypoint_count={len(waypoints)}"

    return set_waypoints


def create_cancel_navigation(bridge, mission_state):
    @tool(extras={"requires_navigation": True})
    def cancel_navigation(reason: str) -> str:
        """Cancel the active Nav2 route before starting a different route."""
        if not bridge.cancel_navigation():
            return "navigation_not_active"
        remaining_count, travelled_path = bridge.route_progress()
        if mission_state.active_task is not None:
            mission_state.save_route_progress(
                remaining_count, travelled_path
            )
        return (
            f"navigation_cancellation_requested: reason={reason}, "
            f"remaining_waypoints={remaining_count}"
        )

    return cancel_navigation
