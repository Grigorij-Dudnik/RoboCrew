"""LLM agent for a waypoint-controlled drone."""

from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.utils import basic_augmentation
from robocrew.robots.WaypointDrone.bridge import DroneObservation, DroneRosBridge
from robocrew.robots.WaypointDrone.map_utils import FlightMapState, draw_normalized_grid_on_map


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
        in_flight_monitor_agent: WaypointDroneAgent | None = None,
        is_in_flight_monitor: bool = False,
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
        self.in_flight_monitor_agent = in_flight_monitor_agent
        self.is_in_flight_monitor = is_in_flight_monitor
        self._all_navigation_tools = list(self.tools)
        self._bind_navigation_mode_tools()

    def main_loop_content(self):
        flight_observation = self.ros_bridge.get_observation()
        return self.process_observation(flight_observation)

    def execute_tool_calls(self, tool_calls):
        result = super().execute_tool_calls(tool_calls)
        if self.ros_bridge:
            self.navigation_mode = self.ros_bridge.navigation_mode
        self._bind_navigation_mode_tools()
        return result

    def _bind_navigation_mode_tools(self):
        visible_tools = [
            tool
            for tool in self._all_navigation_tools
            if (tool.extras or {}).get("mode") in (None, self.navigation_mode)
        ]
        self.bind_tools(visible_tools, tool_choice="any" if visible_tools else None)

    def messages_for_model(self):
        if self.is_in_flight_monitor:
            return super().messages_for_model()
        current_index = max(
            index
            for index, message in enumerate(self.message_history)
            if isinstance(message, HumanMessage)
        )
        events = []
        for message in self.message_history[:current_index]:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    name = call.get("name", "tool")
                    args = call.get("args", {})
                    if name == "set_waypoints":
                        events.append(
                            f"planned {len(args.get('waypoints', []))} waypoints; "
                            f"strategy={args.get('strategy', '')[:180]}"
                        )
                    else:
                        events.append(f"called {name}")
            elif isinstance(message, ToolMessage):
                events.append(f"result: {str(message.content)[:220]}")
        summary = "No earlier navigation events." if not events else "\n".join(
            f"- {event}" for event in events[-8:]
        )
        memory = HumanMessage(
            "Deterministic prior-flight memory (text only; never reuse old coordinates):\n"
            f"{summary}\nThe latest observation below is authoritative."
        )
        return [self.system_message, memory, self.message_history[current_index]]

    def process_observation(self, flight_observation: DroneObservation):
        self.flight_map_state.record_observation(flight_observation)
        if self.is_in_flight_monitor and flight_observation.route_state != "executing":
            return flight_observation.route_state
        if self.is_in_flight_monitor:
            self.message_history = [self.system_message]
        annotated_map_image_b64 = self.flight_map_state.draw_flight_paths_on_map(flight_observation)
        if not self.is_in_flight_monitor:
            annotated_map_image_b64 = draw_normalized_grid_on_map(annotated_map_image_b64)
        if self.in_flight_monitor_agent:
            self.in_flight_monitor_agent.task = self.task
        front_image_b64 = flight_observation.front_image_b64
        if self.navigation_mode == "precision":
            front_image_b64 = self._add_precision_angle_grid(front_image_b64)
        grid_legend = (
            " Grid lines are spaced by 0.1; x increases left-to-right and y top-to-bottom."
            if not self.is_in_flight_monitor
            else ""
        )
        message_content = [{"type": "text", "text": "Front camera view:"}]
        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{front_image_b64}"},
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
                    "BLUE = planned future route from the drone. "
                    f"The yellow center marker shows current position and heading.{grid_legend}\n"
                    f"Height: {flight_observation.height_m} m\n"
                    f"Navigation mode: {self.navigation_mode}"
                ),
            }
        )
        if self.task:
            message_content.append({"type": "text", "text": f"\n\nYour task is: '{self.task}'"})

        return self.invoke_llm_with_message(HumanMessage(message_content))

    def _add_precision_angle_grid(self, front_image_b64: str) -> str:
        front_image = cv2.imdecode(
            np.frombuffer(base64.b64decode(front_image_b64), np.uint8),
            cv2.IMREAD_COLOR,
        )
        augmented_image = basic_augmentation(
            front_image,
            h_fov=self.camera_fov,
            navigation_mode="normal",
        )
        return base64.b64encode(cv2.imencode(".jpg", augmented_image)[1]).decode()
