from robocrew.robots.WaypointDrone.drone_bridge_common import DroneBridge, DroneObservation
from robocrew.robots.WaypointDrone.in_flight_monitor_agent import (
    InFlightMonitorAgent,
    InFlightMonitorState,
)
from robocrew.robots.WaypointDrone.map_utils import FlightMapState
from robocrew.robots.WaypointDrone.tools import (
    create_continue_route,
    create_finish_task,
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
    "InFlightMonitorAgent",
    "DroneBridge",
    "DroneObservation",
    "IsaacRosBridge",
    "MavsdkDroneBridge",
    "FlightMapState",
    "create_set_waypoints",
    "create_finish_task",
    "create_move_forward",
    "create_turn_left",
    "create_turn_right",
    "create_go_to_precision_mode",
    "create_go_to_normal_mode",
    "InFlightMonitorState",
    "create_continue_route",
    "create_stop_route",
]


def __getattr__(name):
    if name == "WaypointDroneAgent":
        from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

        return WaypointDroneAgent
    if name == "IsaacRosBridge":
        from robocrew.robots.WaypointDrone.drone_bridge_isaac_ros import IsaacRosBridge

        return IsaacRosBridge
    if name == "MavsdkDroneBridge":
        from robocrew.robots.WaypointDrone.drone_bridge_real import MavsdkDroneBridge

        return MavsdkDroneBridge
    raise AttributeError(name)
