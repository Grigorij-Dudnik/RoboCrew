"""Agent and route supervision for in-flight monitoring."""

from __future__ import annotations

from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.WaypointDrone.drone_bridge_common import DroneObservation
from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent


class InFlightMonitorAgent(WaypointDroneAgent):
    """Evaluate each executing-route observation independently."""

    def __init__(self, *args, monitor_state, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor_state = monitor_state

    def messages_for_model(self):
        return LLMAgent.messages_for_model(self)

    def process_observation(self, flight_observation: DroneObservation):
        self.flight_map_state.record_observation(flight_observation)
        if flight_observation.route_state != "executing":
            return flight_observation.route_state
        self.message_history = [self.system_message]
        map_image_b64 = self.flight_map_state.draw_flight_paths_on_map(flight_observation)
        message = self._observation_message(flight_observation, map_image_b64)
        return self.invoke_llm_with_message(message)

    def monitor_active_route(self):
        last_observation_number = self.drone_bridge.observation_number
        self.monitor_state.decision = None
        self.monitor_state.stop_reason = ""

        while self.drone_bridge.route_active:
            flight_observation, last_observation_number = self.drone_bridge.wait_for_observation(
                last_observation_number
            )
            if not self.drone_bridge.route_active:
                break

            self.monitor_state.decision = None
            self.process_observation(flight_observation)
            if self.monitor_state.decision == "stop":
                self.drone_bridge.stop_route()
                self.drone_bridge.wait_for_route_end()
                break

        final_observation = self.drone_bridge.latest_observation
        self.flight_map_state.record_observation(final_observation)
        return final_observation.route_state, self.monitor_state.stop_reason


class InFlightMonitorState:
    def __init__(self):
        self.decision: str | None = None
        self.stop_reason = ""
