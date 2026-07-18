"""In-flight route and mission monitoring."""

from __future__ import annotations


class InFlightMonitorState:
    def __init__(self):
        self.decision: str | None = None
        self.stop_reason = ""


class InFlightMonitorSupervisor:
    def __init__(self, ros_bridge, monitor_agent, flight_map_state, monitor_state):
        self.ros_bridge = ros_bridge
        self.monitor_agent = monitor_agent
        self.flight_map_state = flight_map_state
        self.monitor_state = monitor_state

    def monitor_active_route(self):
        active_route_id = self.ros_bridge.current_route_id
        last_observation_sequence = self.ros_bridge.observation_sequence
        final_observation = None
        self.monitor_state.decision = None
        self.monitor_state.stop_reason = ""

        while self.ros_bridge.current_route_id == active_route_id and self.ros_bridge.route_active:
            flight_observation, last_observation_sequence = self.ros_bridge.wait_for_observation(
                last_observation_sequence
            )
            if self.ros_bridge.current_route_id != active_route_id or not self.ros_bridge.route_active:
                break

            self.monitor_state.decision = None
            self.monitor_agent.process_observation(flight_observation)
            if self.monitor_state.decision == "stop":
                self.ros_bridge.stop_route(self.monitor_state.stop_reason)
                final_observation = self.ros_bridge.wait_for_route_end(active_route_id)
                break

        final_observation = final_observation or self.ros_bridge.latest_observation
        self.flight_map_state.record_observation(final_observation)
        return final_observation.route_state, self.monitor_state.stop_reason
