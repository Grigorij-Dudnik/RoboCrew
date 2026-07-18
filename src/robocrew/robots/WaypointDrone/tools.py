"""Waypoint drone tools."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.tools import tool


class RequiredRouteWaypoint(TypedDict):
    x: float
    y: float


class RouteWaypoint(RequiredRouteWaypoint, total=False):
    purpose: str


def create_continue_route(monitor_state):
    @tool
    def continue_route() -> str:
        """Report that active route monitoring may continue."""
        if monitor_state.decision != "stop":
            monitor_state.decision = "continue"
        return "No alert."

    return continue_route


def create_stop_route(monitor_state):
    @tool
    def stop_route(reason: str) -> str:
        """Request an immediate emergency stop for a hazard or mission-relevant observation."""
        monitor_state.decision = "stop"
        monitor_state.stop_reason = reason
        return f"Stopping route: {reason}"

    return stop_route


def create_set_waypoints(
    ros_bridge,
    monitor_supervisor=None,
    flight_map_state=None,
    silent=False,
    mode=None,
):
    @tool(extras={"silent": silent, "mode": mode})
    def set_waypoints(
        situation_reassessment: Annotated[
            str,
            "Write this first. Compare the current camera and map with previous observations and route; "
            "summarize the current situation, covered path, changes, and what remains. If there is no previous route, say so.",
        ],
        strategy: Annotated[
            str,
            "After the reassessment, explain the next route and why.",
        ],
        *,
        waypoints: Annotated[
            list[RouteWaypoint],
            "After completing the strategy, trace the full useful route on the CURRENT map. Add a "
            "waypoint at each meaningful bend, boundary corner, transition, or coverage turn so every "
            "connecting segment stays on task-compatible visible space. Use one only for a short, "
            "straight, unobstructed segment.",
        ],
        altitude_m: float | None = None,
    ) -> str:
        """Reassess the situation, then plan a normalized-map route."""
        if ros_bridge.navigation_mode != "normal":
            return "Waypoint navigation is available only in normal mode. Call go_to_normal_mode first."
        if not waypoints:
            raise ValueError("waypoints must contain at least one waypoint")
        if ros_bridge.route_active:
            return "A route is already active."

        print(f"Situation reassessment: {situation_reassessment}")
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
        if not monitor_supervisor:
            return "Route submitted."
        route_state, stop_reason = monitor_supervisor.monitor_active_route()
        if route_state == "stopped":
            return f"Route stopped by safety checker: {stop_reason}"
        return f"Route {route_state}."

    return set_waypoints


def create_move_forward(ros_bridge, mode=None):
    @tool(extras={"mode": mode})
    def move_forward(distance_meters: float) -> str:
        """In precision mode, fly forward by a visually safe distance in meters."""
        if ros_bridge.navigation_mode != "precision":
            return "Relative movement is available only in precision mode. Call go_to_precision_mode first."
        if ros_bridge.route_active:
            return "A flight command is already active."
        submission = ros_bridge.move_forward(float(distance_meters))
        observation = ros_bridge.wait_for_route_end(submission["route_id"])
        return f"Moved forward {float(distance_meters)} meters. Motion {observation.route_state}."

    return move_forward


def create_turn_left(ros_bridge, mode=None):
    @tool(extras={"mode": mode})
    def turn_left(angle_degrees: float) -> str:
        """In precision mode, turn left by a visually chosen angle in degrees."""
        if ros_bridge.navigation_mode != "precision":
            return "Relative movement is available only in precision mode. Call go_to_precision_mode first."
        if ros_bridge.route_active:
            return "A flight command is already active."
        submission = ros_bridge.turn_left(float(angle_degrees))
        observation = ros_bridge.wait_for_route_end(submission["route_id"])
        return f"Turned left {float(angle_degrees)} degrees. Motion {observation.route_state}."

    return turn_left


def create_turn_right(ros_bridge, mode=None):
    @tool(extras={"mode": mode})
    def turn_right(angle_degrees: float) -> str:
        """In precision mode, turn right by a visually chosen angle in degrees."""
        if ros_bridge.navigation_mode != "precision":
            return "Relative movement is available only in precision mode. Call go_to_precision_mode first."
        if ros_bridge.route_active:
            return "A flight command is already active."
        submission = ros_bridge.turn_right(float(angle_degrees))
        observation = ros_bridge.wait_for_route_end(submission["route_id"])
        return f"Turned right {float(angle_degrees)} degrees. Motion {observation.route_state}."

    return turn_right


def create_go_to_precision_mode(ros_bridge, mode=None):
    @tool(extras={"mode": mode})
    def go_to_precision_mode() -> str:
        """Switch to precision mode for close-distance forward movement and turns."""
        if ros_bridge.route_active:
            return "Cannot switch navigation mode while a flight command is active."
        ros_bridge.set_navigation_mode("precision")
        return "Drone set to precision mode."

    return go_to_precision_mode


def create_go_to_normal_mode(ros_bridge, mode=None):
    @tool(extras={"mode": mode})
    def go_to_normal_mode() -> str:
        """Switch to normal mode for long-distance waypoint navigation."""
        if ros_bridge.route_active:
            return "Cannot switch navigation mode while a flight command is active."
        ros_bridge.set_navigation_mode("normal")
        return "Drone set to normal mode."

    return go_to_normal_mode
