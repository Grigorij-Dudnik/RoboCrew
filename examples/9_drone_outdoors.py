"""Waypoint drone example using ROS2 route execution."""

from pathlib import Path

from robocrew.core.tools import finish_task
from robocrew.robots.WaypointDrone.bridge import DroneRosBridge
from robocrew.robots.WaypointDrone.map_utils import FlightMapState
from robocrew.robots.WaypointDrone.tools import (
    FlightSafetySupervisor,
    SafetyCheckState,
    create_continue_route,
    create_set_waypoints,
    create_stop_route,
)
from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent


ros_bridge = DroneRosBridge()
flight_map_state = FlightMapState()
safety_state = SafetyCheckState()
prompt_dir = Path(__file__).parent.parent / "src/robocrew/robots/WaypointDrone"

safety_checker_agent = WaypointDroneAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    name="Safety Checker",
    tools=[
        create_continue_route(safety_state),
        create_stop_route(safety_state),
    ],
    ros_bridge=ros_bridge,
    flight_map_state=flight_map_state,
    system_prompt=(prompt_dir / "safety_checker.prompt").read_text(encoding="utf-8"),
    is_safety_checker=True,
)
safety_supervisor = FlightSafetySupervisor(
    ros_bridge,
    safety_checker_agent,
    flight_map_state,
    safety_state,
)

mission_agent = WaypointDroneAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    name="Mission Agent",
    tools=[
        create_set_waypoints(ros_bridge, safety_supervisor, flight_map_state),
        finish_task,
    ],
    ros_bridge=ros_bridge,
    flight_map_state=flight_map_state,
    safety_checker_agent=safety_checker_agent,
    history_len=20,
)

mission_agent.task = "Inspect the 5 different roofs of the buildings around you."
mission_agent.go()
