from robocrew.robots.WaypointDrone.bridge import DroneObservation, DroneRosBridge
from robocrew.robots.WaypointDrone.map_utils import FlightMapState
from robocrew.robots.WaypointDrone.tools import (
    FlightSafetySupervisor,
    SafetyCheckState,
    create_continue_route,
    create_set_waypoints,
    create_stop_route,
)

__all__ = [
    "WaypointDroneAgent",
    "DroneObservation",
    "DroneRosBridge",
    "FlightMapState",
    "create_set_waypoints",
    "SafetyCheckState",
    "FlightSafetySupervisor",
    "create_continue_route",
    "create_stop_route",
]


def __getattr__(name):
    if name == "WaypointDroneAgent":
        from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

        return WaypointDroneAgent
    raise AttributeError(name)
