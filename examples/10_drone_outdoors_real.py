"""Waypoint-drone mission and in-flight monitor agents on a real drone."""

from pathlib import Path

from robocrew.robots.WaypointDrone.in_flight_monitor_agent import (
    InFlightMonitorAgent,
    InFlightMonitorState,
)
from robocrew.robots.WaypointDrone.map_utils import FlightMapState
from robocrew.robots.WaypointDrone.drone_bridge_real import MavsdkDroneBridge
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
from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent


drone = MavsdkDroneBridge()
flight_map_state = FlightMapState()
monitor_state = InFlightMonitorState()
prompt_dir = Path(__file__).parent.parent / "src/robocrew/robots/WaypointDrone"

in_flight_monitor_agent = InFlightMonitorAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    name="In-Flight Monitor",
    tools=[
        create_continue_route(monitor_state),
        create_stop_route(monitor_state),
    ],
    drone_bridge=drone,
    flight_map_state=flight_map_state,
    monitor_state=monitor_state,
    system_prompt=(prompt_dir / "in_flight_monitor.prompt").read_text(encoding="utf-8"),
)

mission_agent = WaypointDroneAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    name="Mission Agent",
    tools=[
        create_set_waypoints(drone, in_flight_monitor_agent, flight_map_state),
        create_move_forward(drone),
        create_turn_left(drone),
        create_turn_right(drone),
        create_go_to_precision_mode(drone),
        create_go_to_normal_mode(drone),
        create_finish_task(drone),
    ],
    drone_bridge=drone,
    flight_map_state=flight_map_state,
    in_flight_monitor_agent=in_flight_monitor_agent,
    system_prompt=(prompt_dir / "dual_mode_drone.prompt").read_text(encoding="utf-8"),
    history_len=20,
)

mission_agent.task = "A human is lost somewhere on the map, probably on an asphalt road. Search the road network efficiently without repeating the same road unless necessary. Fly below 30 meters. Follow the roads, never go on top of buildings."
drone.takeoff()
mission_agent.go()
