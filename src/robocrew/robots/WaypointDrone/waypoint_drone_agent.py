"""LLM agent for a waypoint-controlled drone."""

from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage

from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.WaypointDrone.bridge import DroneObservation, DroneRosBridge
from robocrew.robots.WaypointDrone.map_utils import FlightMapState


class WaypointDroneAgent(LLMAgent):
    """LLMAgent child for a ROS2-driven waypoint drone."""

    def __init__(
        self,
        model: str,
        tools: list | None = None,
        name: str | None = None,
        ros_bridge: DroneRosBridge | None = None,
        system_prompt: str | None = None,
        history_len: int | None = None,
        flight_map_state: FlightMapState | None = None,
        safety_checker_agent: WaypointDroneAgent | None = None,
        is_safety_checker: bool = False,
    ):
        super().__init__(
            model=model,
            tools=tools or [],
            main_camera=None,
            name=name,
            system_prompt=system_prompt or Path(__file__).with_name("waypoint_drone.prompt").read_text(encoding="utf-8"),
            camera_fov=90,
            history_len=history_len,
        )
        self.ros_bridge = ros_bridge
        self.flight_map_state = flight_map_state or FlightMapState()
        self.safety_checker_agent = safety_checker_agent
        self.is_safety_checker = is_safety_checker

    def main_loop_content(self):
        flight_observation = self.ros_bridge.get_observation()
        return self.process_observation(flight_observation)

    def process_observation(self, flight_observation: DroneObservation):
        self.flight_map_state.record_observation(flight_observation)
        if self.is_safety_checker and flight_observation.route_state != "executing":
            return flight_observation.route_state
        if self.is_safety_checker:
            self.message_history = [self.system_message]
        annotated_map_image_b64 = self.flight_map_state.draw_flight_paths_on_map(flight_observation)
        if self.safety_checker_agent:
            self.safety_checker_agent.task = self.task
        message_content = [{"type": "text", "text": "Front camera view:"}]
        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{flight_observation.front_image_b64}"},
            }
        )
        message_content.append({"type": "text", "text": "\n\nMap view:"})
        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{annotated_map_image_b64}"},
            }
        )
        message_content.append(
            {
                "type": "text",
                "text": (
                    "\n\nMap legend: RED = route already flown; "
                    "BLUE = remaining future route from the drone. "
                    "The yellow center marker shows current position and heading.\n"
                    f"Height: {flight_observation.height_m} m"
                ),
            }
        )
        if self.task:
            message_content.append({"type": "text", "text": f"\n\nYour task is: '{self.task}'"})

        return self.invoke_llm_with_message(HumanMessage(message_content))
