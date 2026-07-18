from robocrew.robots.WaypointDrone.bridge import DroneObservation, DroneRosBridge
from robocrew.robots.WaypointDrone.map_utils import FlightMapState
from robocrew.robots.WaypointDrone.monitoring import InFlightMonitorState, InFlightMonitorSupervisor
from robocrew.robots.WaypointDrone.tools import (
    create_continue_route,
    create_go_to_normal_mode,
    create_go_to_precision_mode,
    create_move_forward,
    create_set_waypoints,
    create_stop_route,
    create_turn_left,
    create_turn_right,
)

__all__ = [
    "WaypointDroneAgent",
    "DroneObservation",
    "DroneRosBridge",
    "FlightMapState",
    "create_set_waypoints",
    "create_move_forward",
    "create_turn_left",
    "create_turn_right",
    "create_go_to_precision_mode",
    "create_go_to_normal_mode",
    "InFlightMonitorState",
    "InFlightMonitorSupervisor",
    "create_continue_route",
    "create_stop_route",
]


def __getattr__(name):
    if name == "WaypointDroneAgent":
        from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

        return WaypointDroneAgent
    raise AttributeError(name)
