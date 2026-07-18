"""Waypoint drone example using ROS2 route execution."""

from pathlib import Path

from robocrew.core.tools import finish_task
from robocrew.robots.WaypointDrone.bridge import DroneRosBridge
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
from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent


ros_bridge = DroneRosBridge()
flight_map_state = FlightMapState()
monitor_state = InFlightMonitorState()
prompt_dir = Path(__file__).parent.parent / "src/robocrew/robots/WaypointDrone"

in_flight_monitor_agent = WaypointDroneAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    name="In-Flight Monitor",
    tools=[
        create_continue_route(monitor_state),
        create_stop_route(monitor_state),
    ],
    ros_bridge=ros_bridge,
    flight_map_state=flight_map_state,
    system_prompt=(prompt_dir / "in_flight_monitor.prompt").read_text(encoding="utf-8"),
    is_in_flight_monitor=True,
)
monitor_supervisor = InFlightMonitorSupervisor(
    ros_bridge,
    in_flight_monitor_agent,
    flight_map_state,
    monitor_state,
)

mission_agent = WaypointDroneAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    name="Mission Agent",
    tools=[
        create_set_waypoints(
            ros_bridge,
            monitor_supervisor,
            flight_map_state,
            silent=True,
            mode="normal",
        ),
        create_move_forward(ros_bridge, mode="precision"),
        create_turn_left(ros_bridge, mode="precision"),
        create_turn_right(ros_bridge, mode="precision"),
        create_go_to_precision_mode(ros_bridge, mode="normal"),
        create_go_to_normal_mode(ros_bridge, mode="precision"),
        finish_task,
    ],
    ros_bridge=ros_bridge,
    flight_map_state=flight_map_state,
    in_flight_monitor_agent=in_flight_monitor_agent,
    system_prompt=(prompt_dir / "dual_mode_drone.prompt").read_text(encoding="utf-8"),
    history_len=20,
)

mission_agent.task = "A human is lost somewhere on the map, probably on an asphalt road. Search the road network efficiently without repeating the same road unless necessary. Fly below 30 meters. Follow the roads, never go on top of buildings."
mission_agent.go()
