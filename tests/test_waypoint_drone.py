import base64
import os
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
sys.modules.setdefault("pygame", MagicMock())

import langchain.chat_models
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

setattr(langchain.chat_models, "init_chat_model", MagicMock())

from robocrew.core.tools import finish_task
from robocrew.robots.WaypointDrone.drone_bridge_common import DroneObservation
from robocrew.robots.WaypointDrone.drone_bridge_isaac_ros import IsaacRosBridge
from robocrew.robots.WaypointDrone.map_utils import (
    draw_flight_paths_on_map,
    draw_normalized_grid_on_map,
    normalized_waypoints_to_gps,
)
from robocrew.robots.WaypointDrone.in_flight_monitor_agent import (
    InFlightMonitorAgent,
    InFlightMonitorState,
)
from robocrew.robots.WaypointDrone.tools import (
    create_go_to_normal_mode,
    create_go_to_precision_mode,
    create_move_forward,
    create_set_waypoints,
    create_turn_left,
    create_turn_right,
)


class FakeRosBridge:
    def __init__(self):
        self.navigation_mode = "normal"
        self.route_active = False
        self.set_waypoints_calls = []
        self.relative_motion_calls = []
        self.reused_observation = False

    def set_waypoints(self, route_waypoints, altitude_m=None, strategy=None):
        self.set_waypoints_calls.append((route_waypoints, altitude_m, strategy))
        return {
            "current_gps": {"lat": 52.0, "lon": 21.0, "alt": 15.0},
        }

    def set_navigation_mode(self, navigation_mode):
        self.navigation_mode = navigation_mode
        self.reused_observation = True

    def move_forward(self, distance_meters):
        self.relative_motion_calls.append(("move_forward", distance_meters))

    def turn_left(self, angle_degrees):
        self.relative_motion_calls.append(("turn_left", angle_degrees))

    def turn_right(self, angle_degrees):
        self.relative_motion_calls.append(("turn_right", angle_degrees))

    def wait_for_route_end(self):
        return DroneObservation(route_state="completed")


class TestWaypointDroneTools(unittest.TestCase):
    def test_set_waypoints_accepts_arbitrary_non_empty_route(self):
        ros_bridge = FakeRosBridge()
        tool = create_set_waypoints(ros_bridge)
        waypoints = [
            {"x": 0.1, "y": 0.2, "purpose": "enter open space"},
            {"x": 0.3, "y": 0.4},
            {"x": 0.5, "y": 0.6},
        ]

        strategy = (
            "The previous views showed an uninspected roof ahead-left and open space leading to it. "
            "Approach that roof through the open area before selecting another target."
        )
        situation_reassessment = (
            "The previous route covered the road behind the drone. The current view shows the drone "
            "beside that completed section with an uninspected roof ahead-left."
        )
        with patch("builtins.print") as mock_print:
            tool_result = tool.invoke(
                {
                    "situation_reassessment": situation_reassessment,
                    "strategy": strategy,
                    "waypoints": waypoints,
                    "altitude_m": 22.0,
                }
            )

        self.assertEqual(
            ros_bridge.set_waypoints_calls,
            [(waypoints, 22.0, strategy)],
        )
        self.assertEqual(
            [call.args[0] for call in mock_print.call_args_list[:3]],
            [
                f"Situation reassessment: {situation_reassessment}",
                f"Strategy: {strategy}",
                "Waypoints:",
            ],
        )
        self.assertIn("Route submitted", tool_result)
        self.assertNotIn("Executed GPS coordinate array", tool_result)
        self.assertNotIn("52.0", tool_result)

    def test_set_waypoints_rejects_empty_route(self):
        tool = create_set_waypoints(FakeRosBridge())

        with self.assertRaises(ValueError):
            tool.invoke(
                {
                    "situation_reassessment": "No previous route; the current route area is blocked.",
                    "strategy": "No safe route is currently visible.",
                    "waypoints": [],
                }
            )

    def test_set_waypoints_suppresses_only_the_generic_call_log(self):
        tool = create_set_waypoints(FakeRosBridge())

        with patch("builtins.print") as mock_print:
            tool.invoke(
                {
                    "situation_reassessment": "No previous route; an open road is visible ahead.",
                    "strategy": "Search the open road.",
                    "waypoints": [{"x": 0.5, "y": 0.25}],
                }
            )

        self.assertTrue(tool.extras["silent"])
        self.assertEqual(
            [call.args[0] for call in mock_print.call_args_list],
            [
                "Situation reassessment: No previous route; an open road is visible ahead.",
                "Strategy: Search the open road.",
                "Waypoints:",
                "1. x=0.5, y=0.25",
            ],
        )

    def test_set_waypoints_schema_orders_reassessment_before_strategy_and_waypoints(self):
        tool_schema = create_set_waypoints(FakeRosBridge()).args_schema.model_json_schema()

        self.assertEqual(
            list(tool_schema["properties"]),
            ["situation_reassessment", "strategy", "waypoints", "altitude_m"],
        )
        self.assertEqual(
            tool_schema["required"],
            ["situation_reassessment", "strategy", "waypoints"],
        )
        self.assertIn("Reassess the situation", tool_schema["description"])
        self.assertIn(
            "Compare the current camera and map with previous observations and route",
            tool_schema["properties"]["situation_reassessment"]["description"],
        )
        self.assertIn(
            "After the reassessment",
            tool_schema["properties"]["strategy"]["description"],
        )
        self.assertIn(
            "every connecting segment stays on task-compatible visible space",
            tool_schema["properties"]["waypoints"]["description"],
        )
        waypoint_schema = tool_schema["$defs"]["RouteWaypoint"]
        self.assertEqual(list(waypoint_schema["properties"]), ["x", "y", "purpose"])
        self.assertEqual(waypoint_schema["required"], ["x", "y"])

    def test_navigation_modes_are_enforced(self):
        ros_bridge = FakeRosBridge()

        self.assertIn(
            "only in precision mode",
            create_move_forward(ros_bridge).invoke({"distance_meters": 2.0}),
        )
        self.assertEqual(
            create_go_to_precision_mode(ros_bridge).invoke({}),
            "Drone set to precision mode.",
        )
        self.assertTrue(ros_bridge.reused_observation)
        self.assertIn(
            "only in normal mode",
            create_set_waypoints(ros_bridge).invoke(
                {
                    "situation_reassessment": "The previous route is complete; open road remains ahead.",
                    "strategy": "Continue the search.",
                    "waypoints": [{"x": 0.5, "y": 0.5}],
                }
            ),
        )
        self.assertEqual(
            create_go_to_normal_mode(ros_bridge).invoke({}),
            "Drone set to normal mode.",
        )

    def test_precision_tools_submit_motion_and_wait_for_completion(self):
        ros_bridge = FakeRosBridge()
        ros_bridge.navigation_mode = "precision"

        results = [
            create_move_forward(ros_bridge).invoke({"distance_meters": 2.5}),
            create_turn_left(ros_bridge).invoke({"angle_degrees": 15.0}),
            create_turn_right(ros_bridge).invoke({"angle_degrees": 20.0}),
        ]

        self.assertEqual(
            ros_bridge.relative_motion_calls,
            [
                ("move_forward", 2.5),
                ("turn_left", 15.0),
                ("turn_right", 20.0),
            ],
        )
        self.assertTrue(all("completed" in result for result in results))

    def test_mode_switch_is_rejected_during_active_motion(self):
        ros_bridge = FakeRosBridge()
        ros_bridge.route_active = True

        result = create_go_to_precision_mode(ros_bridge).invoke({})

        self.assertIn("while a flight command is active", result)
        self.assertEqual(ros_bridge.navigation_mode, "normal")


class TestInFlightMonitorAgent(unittest.TestCase):
    def test_stops_route_and_waits_for_final_observation(self):
        executing_observation = DroneObservation(route_state="executing")
        stopped_observation = DroneObservation(route_state="stopped")
        monitor_state = InFlightMonitorState()

        ros_bridge = MagicMock()
        ros_bridge.route_active = True
        ros_bridge.observation_number = 0
        ros_bridge.latest_observation = executing_observation
        ros_bridge.wait_for_observation.return_value = (executing_observation, 1)
        ros_bridge.wait_for_route_end.return_value = stopped_observation

        monitor_agent = InFlightMonitorAgent.__new__(InFlightMonitorAgent)
        monitor_agent.drone_bridge = ros_bridge
        monitor_agent.monitor_state = monitor_state
        monitor_agent.process_observation = MagicMock()
        monitor_agent.process_observation.side_effect = lambda _observation: (
            setattr(monitor_state, "decision", "stop"),
            setattr(monitor_state, "stop_reason", "Tree ahead"),
        )
        flight_map_state = MagicMock()
        monitor_agent.flight_map_state = flight_map_state
        ros_bridge.wait_for_route_end.side_effect = lambda: setattr(
            ros_bridge, "latest_observation", stopped_observation
        )

        self.assertEqual(monitor_agent.monitor_active_route(), ("stopped", "Tree ahead"))
        monitor_agent.process_observation.assert_called_once_with(executing_observation)
        ros_bridge.stop_route.assert_called_once_with()
        ros_bridge.wait_for_route_end.assert_called_once_with()
        flight_map_state.record_observation.assert_called_once_with(stopped_observation)


class TestWaypointDroneMapUtils(unittest.TestCase):
    def test_normalized_grid_preserves_map_size_and_marks_tenths(self):
        encoded_map = cv2.imencode(".jpg", np.zeros((100, 200, 3), dtype=np.uint8))[1]
        map_image_b64 = base64.b64encode(encoded_map).decode()

        grid_image = cv2.imdecode(
            np.frombuffer(base64.b64decode(draw_normalized_grid_on_map(map_image_b64)), np.uint8),
            cv2.IMREAD_COLOR,
        )

        self.assertEqual(grid_image.shape, (100, 200, 3))
        self.assertGreater(grid_image[50, 20].max(), 0)
        self.assertGreater(grid_image[10, 100].max(), 0)

    def test_normalized_waypoints_are_relative_to_moving_map_center(self):
        center = {"lat": 52.0, "lon": 21.0}
        gps_waypoints = normalized_waypoints_to_gps(
            [{"x": 0.5, "y": 0.5}, {"x": 0.5, "y": 0.0}], center, 300.0
        )

        self.assertEqual(gps_waypoints[0], center)
        self.assertAlmostEqual((gps_waypoints[1]["lat"] - center["lat"]) * 111_320.0, 150.0)
        self.assertEqual(gps_waypoints[1]["lon"], center["lon"])

    def test_heading_marker_is_drawn_after_route_lines(self):
        encoded_map = cv2.imencode(".jpg", np.zeros((100, 100, 3), dtype=np.uint8))[1]
        map_image_b64 = base64.b64encode(encoded_map).decode()
        draw_order = []

        with (
            patch(
                "robocrew.robots.WaypointDrone.map_utils.cv2.polylines",
                side_effect=lambda image, *_args, **_kwargs: draw_order.append("line") or image,
            ),
            patch(
                "robocrew.robots.WaypointDrone.map_utils.cv2.fillPoly",
                side_effect=lambda image, *_args, **_kwargs: draw_order.append("arrow") or image,
            ),
        ):
            draw_flight_paths_on_map(
                map_image_b64,
                {"lat": 52.0, "lon": 21.0},
                300.0,
                [{"lat": 52.0, "lon": 21.0}, {"lat": 52.0001, "lon": 21.0}],
                [{"lat": 52.0, "lon": 21.0001}],
                yaw_rad=0.5,
            )

        self.assertEqual(draw_order, ["line", "line", "arrow"])


class TestWaypointDroneBridge(unittest.TestCase):
    def test_mode_switch_reuses_latest_observation_once(self):
        bridge = IsaacRosBridge.__new__(IsaacRosBridge)
        bridge.latest_observation = DroneObservation(gps={"lat": 52.0, "lon": 21.0})
        bridge._observation_changed = MagicMock()
        bridge._observation_changed.__enter__.return_value = bridge._observation_changed

        bridge.set_navigation_mode("precision")
        observation = bridge.get_observation()

        self.assertIs(observation, bridge.latest_observation)
        self.assertEqual(bridge.navigation_mode, "precision")
        self.assertFalse(bridge._reuse_latest_observation)

    def test_get_observation_waits_for_first_message(self):
        bridge = IsaacRosBridge.__new__(IsaacRosBridge)
        bridge.latest_observation = DroneObservation()
        bridge._has_observation = False
        bridge._reuse_latest_observation = False
        bridge._node = object()
        observation_payload = {
            "front_image_b64": "front-b64",
            "map_image_b64": "map-b64",
            "gps": {"lat": 52.0, "lon": 21.0},
            "height_m": 15.0,
        }
        bridge._rclpy = types.SimpleNamespace(
            spin_once=lambda *_args, **_kwargs: bridge._handle_observation(
                types.SimpleNamespace(data=json.dumps(observation_payload))
            )
        )

        flight_observation = bridge.get_observation()

        self.assertEqual(flight_observation.front_image_b64, "front-b64")

    def test_bridge_publishes_route_request(self):
        published = []

        class String:
            def __init__(self):
                self.data = ""

        class Node:
            def create_publisher(self, *_args):
                publisher = MagicMock()
                publisher.publish.side_effect = published.append
                return publisher

            def create_subscription(self, *_args):
                return MagicMock()

            def destroy_node(self):
                pass

        rclpy = types.SimpleNamespace(ok=lambda: True, init=lambda: None, create_node=lambda _name: Node())
        std_msgs = types.ModuleType("std_msgs")
        std_msgs_msg = types.ModuleType("std_msgs.msg")
        std_msgs_msg.String = String

        with patch.dict(sys.modules, {"rclpy": rclpy, "std_msgs": std_msgs, "std_msgs.msg": std_msgs_msg}):
            bridge = IsaacRosBridge()

        waypoints = [{"x": 0.25, "y": 0.75}]

        bridge.set_waypoints(
            waypoints,
            altitude_m=18.0,
            strategy="Survey the nearest roof.",
        )

        self.assertEqual(len(published), 1)
        command_payload = json.loads(published[0].data)
        self.assertEqual(command_payload["waypoints"], waypoints)
        self.assertEqual(command_payload["altitude_m"], 18.0)
        self.assertEqual(command_payload["strategy"], "Survey the nearest roof.")

    def test_bridge_publishes_relative_motion_request(self):
        published = []

        class String:
            def __init__(self):
                self.data = ""

        bridge = IsaacRosBridge.__new__(IsaacRosBridge)
        bridge._string_msg = String
        bridge._command_pub = MagicMock()
        bridge._command_pub.publish.side_effect = published.append
        bridge.latest_observation = DroneObservation(gps={"lat": 52.0, "lon": 21.0})
        bridge._reuse_latest_observation = True

        bridge.turn_right(25.0)

        command_payload = json.loads(published[0].data)
        self.assertEqual(command_payload["command"], "relative_motion")
        self.assertEqual(command_payload["motion"], "turn_right")
        self.assertEqual(command_payload["angle_degrees"], 25.0)
        self.assertFalse(bridge._reuse_latest_observation)


class TestWaypointDroneAgent(unittest.TestCase):
    def _response(self):
        response = MagicMock()
        response.content = "planning route"
        response.tool_calls = []
        response.usage_metadata = {}
        return response

    def test_agent_message_contains_images_state_and_task(self):
        with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
            llm = MagicMock()
            mock_llm_factory.return_value.bind_tools.return_value = llm
            llm.invoke.return_value = self._response()

            from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

            ros_bridge = MagicMock()
            encoded_map = cv2.imencode(".jpg", np.zeros((100, 160, 3), dtype=np.uint8))[1]
            map_image_b64 = base64.b64encode(encoded_map).decode()
            ros_bridge.get_observation.return_value = DroneObservation(
                front_image_b64="front-b64",
                map_image_b64=map_image_b64,
                gps={"lat": 52.0, "lon": 21.0, "alt": 20.0},
                height_m=20.0,
            )
            mission_agent = WaypointDroneAgent(
                model="fake-model",
                tools=[],
                name="Mission Agent",
                drone_bridge=ros_bridge,
            )
            mission_agent.task = "Inspect the open road."

            mission_agent.main_loop_content()

        human_messages = [
            message
            for message in mission_agent.message_history
            if getattr(message, "type", None) == "human"
        ]
        content = human_messages[0].content
        text = "\n".join(item["text"] for item in content if item["type"] == "text")
        image_urls = [item["image_url"]["url"] for item in content if item["type"] == "image_url"]
        self.assertIn("Front camera view", text)
        self.assertIn("Map view", text)
        self.assertIn("RED = route already flown", text)
        self.assertIn("BLUE = planned future route", text)
        self.assertIn("Grid lines are spaced by 0.1", text)
        self.assertNotIn("Map width:", text)
        self.assertNotIn("Current GPS/location", text)
        self.assertIn("Height: 20.0 m", text)
        self.assertNotIn("Route state:", text)
        self.assertNotIn("Pose:", text)
        self.assertNotIn("Route status:", text)
        self.assertIn("Inspect the open road.", text)
        self.assertIn("data:image/jpeg;base64,front-b64", image_urls)
        self.assertEqual(len(image_urls), 2)
        self.assertTrue(image_urls[1].startswith("data:image/jpeg;base64,"))
        trace_config = llm.invoke.call_args.kwargs["config"]
        self.assertEqual(trace_config["run_name"], "Mission Agent")
        self.assertEqual(trace_config["tags"], ["agent:Mission Agent"])
        self.assertEqual(trace_config["metadata"]["agent_name"], "Mission Agent")

    def test_mission_agent_uses_deterministic_event_memory_without_old_images(self):
        with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
            llm = MagicMock()
            mock_llm_factory.return_value.bind_tools.return_value = llm
            llm.invoke.return_value = self._response()

            from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

            encoded_map = cv2.imencode(".jpg", np.zeros((100, 160, 3), dtype=np.uint8))[1]
            map_image_b64 = base64.b64encode(encoded_map).decode()
            mission_agent = WaypointDroneAgent(model="fake-model", tools=[])
            mission_agent.message_history.extend(
                [
                    HumanMessage(
                        [
                            {"type": "text", "text": "Old observation"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/jpeg;base64,old-image"},
                            },
                        ]
                    ),
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "set_waypoints",
                                "args": {
                                    "situation_reassessment": "Old situation",
                                    "strategy": "Inspect the western roof.",
                                    "waypoints": [{"x": 0.3, "y": 0.4}],
                                },
                                "id": "route-1",
                            }
                        ],
                    ),
                    ToolMessage(content="Route completed.", tool_call_id="route-1"),
                ]
            )

            mission_agent.process_observation(
                DroneObservation(
                    front_image_b64="current-front",
                    map_image_b64=map_image_b64,
                    gps={"lat": 52.0, "lon": 21.0},
                    height_m=20.0,
                )
            )

        model_messages = llm.invoke.call_args.args[0]
        self.assertEqual(len(model_messages), 3)
        self.assertIn("planned 1 waypoints", model_messages[1].content)
        self.assertIn("strategy=Inspect the western roof.", model_messages[1].content)
        self.assertIn("result: Route completed.", model_messages[1].content)
        self.assertNotIn("old-image", str(model_messages))
        self.assertIn("old-image", str(mission_agent.message_history))

    def test_in_flight_monitor_keeps_only_current_observation(self):
        with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
            llm = MagicMock()
            mock_llm_factory.return_value.bind_tools.return_value = llm
            llm.invoke.return_value = self._response()

            from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

            monitor_agent = WaypointDroneAgent(
                model="fake-model",
                tools=[],
                name="In-Flight Monitor",
                is_in_flight_monitor=True,
                history_len=8,
            )
            common_observation = {
                "map_image_b64": "map-b64",
                "gps": {"lat": 52.0, "lon": 21.0},
                "height_m": 20.0,
                "route_state": "executing",
            }

            monitor_agent.process_observation(
                DroneObservation(front_image_b64="old-front", **common_observation)
            )
            monitor_agent.process_observation(
                DroneObservation(front_image_b64="current-front", **common_observation)
            )

        current_messages = llm.invoke.call_args.args[0]
        human_messages = [
            message for message in current_messages if getattr(message, "type", None) == "human"
        ]
        self.assertEqual(len(human_messages), 1)
        image_urls = [
            item["image_url"]["url"]
            for item in human_messages[0].content
            if item["type"] == "image_url"
        ]
        self.assertIn("data:image/jpeg;base64,current-front", image_urls)
        self.assertNotIn("data:image/jpeg;base64,old-front", image_urls)
        self.assertEqual(llm.invoke.call_args.kwargs["config"]["run_name"], "In-Flight Monitor")

    def test_precision_mode_augments_front_image_with_angle_grid(self):
        with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
            llm = MagicMock()
            mock_llm_factory.return_value.bind_tools.return_value = llm
            llm.invoke.return_value = self._response()

            from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

            encoded_image = cv2.imencode(".jpg", np.zeros((100, 160, 3), dtype=np.uint8))[1]
            front_image_b64 = base64.b64encode(encoded_image).decode()
            ros_bridge = MagicMock()
            ros_bridge.navigation_mode = "precision"
            mission_agent = WaypointDroneAgent(
                model="fake-model",
                tools=[],
                drone_bridge=ros_bridge,
            )
            mission_agent.navigation_mode = "precision"

            with patch(
                "robocrew.robots.WaypointDrone.waypoint_drone_agent.basic_augmentation",
                wraps=__import__("robocrew.core.utils", fromlist=["basic_augmentation"]).basic_augmentation,
            ) as mock_augmentation:
                mission_agent.process_observation(
                    DroneObservation(
                        front_image_b64=front_image_b64,
                        map_image_b64=front_image_b64,
                        gps={"lat": 52.0, "lon": 21.0},
                        height_m=15.0,
                    )
                )

        self.assertEqual(mock_augmentation.call_args.kwargs["h_fov"], 90)
        self.assertEqual(mock_augmentation.call_args.kwargs["navigation_mode"], "normal")
        content = [
            message
            for message in mission_agent.message_history
            if getattr(message, "type", None) == "human"
        ][0].content
        text = "\n".join(item["text"] for item in content if item["type"] == "text")
        self.assertIn("Navigation mode: precision", text)

    def test_only_tools_for_current_navigation_mode_are_bound(self):
        with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
            bound_llm = MagicMock()
            mock_llm_factory.return_value.bind_tools.return_value = bound_llm

            from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

            ros_bridge = FakeRosBridge()
            mission_agent = WaypointDroneAgent(
                model="fake-model",
                tools=[
                    create_set_waypoints(ros_bridge),
                    create_move_forward(ros_bridge),
                    create_turn_left(ros_bridge),
                    create_turn_right(ros_bridge),
                    create_go_to_precision_mode(ros_bridge),
                    create_go_to_normal_mode(ros_bridge),
                    finish_task,
                ],
                drone_bridge=ros_bridge,
            )

            self.assertEqual(
                {tool.name for tool in mission_agent.tools},
                {"set_waypoints", "go_to_precision_mode", "finish_task"},
            )
            self.assertEqual(
                {
                    tool.name
                    for tool in mock_llm_factory.return_value.bind_tools.call_args.args[0]
                },
                {"set_waypoints", "go_to_precision_mode", "finish_task"},
            )
            self.assertEqual(
                mock_llm_factory.return_value.bind_tools.call_args.kwargs["tool_choice"],
                "any",
            )

            mission_agent.execute_tool_calls([
                {"name": "go_to_precision_mode", "args": {}, "id": "precision-switch"}
            ])

            self.assertEqual(
                {tool.name for tool in mission_agent.tools},
                {"move_forward", "turn_left", "turn_right", "go_to_normal_mode", "finish_task"},
            )
            self.assertEqual(
                {
                    tool.name
                    for tool in mock_llm_factory.return_value.bind_tools.call_args.args[0]
                },
                {"move_forward", "turn_left", "turn_right", "go_to_normal_mode", "finish_task"},
            )
            self.assertEqual(
                mock_llm_factory.return_value.bind_tools.call_args.kwargs["tool_choice"],
                "any",
            )
            self.assertNotIn("set_waypoints", mission_agent.tool_name_to_tool)
            self.assertNotIn("go_to_precision_mode", mission_agent.tool_name_to_tool)


if __name__ == "__main__":
    unittest.main()
