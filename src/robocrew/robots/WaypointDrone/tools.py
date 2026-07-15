"""Waypoint drone tools."""

from __future__ import annotations

import threading
import time
from typing import Annotated, TypedDict

from langchain_core.tools import tool


class RequiredRouteWaypoint(TypedDict):
    x: float
    y: float


class RouteWaypoint(RequiredRouteWaypoint, total=False):
    purpose: str


class SafetyCheckState:
    def __init__(self):
        self.decision: str | None = None
        self.stop_reason: str = ""
        self.lock = threading.Lock()
        self.next_check_at = 0.0


class FlightSafetySupervisor:
    def __init__(
        self,
        ros_bridge,
        safety_checker_agent,
        flight_map_state,
        safety_state,
        check_interval_s=0.5,
    ):
        self.ros_bridge = ros_bridge
        self.safety_checker_agent = safety_checker_agent
        self.flight_map_state = flight_map_state
        self.safety_state = safety_state
        self.check_interval_s = check_interval_s

    def monitor_active_route(self):
        active_route_id = self.ros_bridge.current_route_id
        monitoring_finished = threading.Event()

        def run_safety_checks():
            last_observation_sequence = self.ros_bridge.observation_sequence
            while self.ros_bridge.current_route_id == active_route_id and self.ros_bridge.route_active:
                with self.safety_state.lock:
                    wait_time_s = self.safety_state.next_check_at - time.monotonic()
                    if monitoring_finished.wait(max(0.0, wait_time_s)):
                        return
                    flight_observation, last_observation_sequence = self.ros_bridge.wait_for_observation(
                        last_observation_sequence
                    )
                    if (
                        self.ros_bridge.current_route_id != active_route_id
                        or not self.ros_bridge.route_active
                        or monitoring_finished.is_set()
                    ):
                        return
                    check_started_at = time.monotonic()
                    self.safety_state.decision = None
                    self.safety_checker_agent.process_observation(flight_observation)
                    self.safety_state.next_check_at = check_started_at + self.check_interval_s
                    if (
                        self.safety_state.decision == "stop"
                        and self.ros_bridge.current_route_id == active_route_id
                        and self.ros_bridge.route_active
                    ):
                        self.ros_bridge.stop_route(self.safety_state.stop_reason)
                        return

        threading.Thread(target=run_safety_checks, daemon=True).start()
        while self.ros_bridge.current_route_id == active_route_id and self.ros_bridge.route_active:
            time.sleep(0.1)
        monitoring_finished.set()
        final_observation = self.ros_bridge.latest_observation
        self.flight_map_state.record_observation(final_observation)
        return final_observation.route_state, self.safety_state.stop_reason


def create_continue_route(safety_state: SafetyCheckState):
    @tool
    def continue_route() -> str:
        """Report that background route monitoring may continue."""
        if safety_state.decision != "stop":
            safety_state.decision = "continue"
        return "No alert."

    return continue_route


def create_stop_route(safety_state: SafetyCheckState):
    @tool
    def stop_route(reason: str) -> str:
        """Request an immediate emergency stop for a hazard or mission-relevant observation."""
        safety_state.decision = "stop"
        safety_state.stop_reason = reason
        return f"Stopping route: {reason}"

    return stop_route


def create_set_waypoints(ros_bridge, safety_supervisor=None, flight_map_state=None):
    @tool
    def set_waypoints(
        strategy: Annotated[
            str,
            "First summarize mission-relevant evidence from previous and current observations; "
            "then explain the next route and why it follows from that evidence.",
        ],
        *,
        waypoints: list[RouteWaypoint],
        altitude_m: float | None = None,
    ) -> str:
        """Summarize accumulated observations, explain the next route, then send normalized map waypoints."""
        if not waypoints:
            raise ValueError("waypoints must contain at least one waypoint")
        if ros_bridge.route_active:
            return "A route is already active."

        print(f"Strategy: {strategy}")
        print("Waypoints:")
        for waypoint_index, waypoint in enumerate(waypoints, start=1):
            waypoint_description = f"{waypoint_index}. x={waypoint['x']}, y={waypoint['y']}"
            if purpose := waypoint.get("purpose"):
                waypoint_description += f" — {purpose}"
            print(waypoint_description)

        submitted_waypoints = (
            flight_map_state.set_planned_route_from_normalized_waypoints(waypoints)
            if flight_map_state
            else list(waypoints)
        )
        ros_bridge.set_waypoints(submitted_waypoints, altitude_m, strategy)
        if not safety_supervisor:
            return "Route submitted."
        route_state, stop_reason = safety_supervisor.monitor_active_route()
        if route_state == "stopped":
            return f"Route stopped by safety checker: {stop_reason}"
        return f"Route {route_state}."

    return set_waypoints
