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

setattr(langchain.chat_models, "init_chat_model", MagicMock())

from robocrew.robots.WaypointDrone.bridge import DroneObservation, DroneRosBridge
from robocrew.robots.WaypointDrone.map_utils import (
    draw_flight_paths_on_map,
    normalized_waypoints_to_gps,
)
from robocrew.robots.WaypointDrone.tools import FlightSafetySupervisor, create_set_waypoints


class FakeRosBridge:
    def __init__(self):
        self.route_active = False
        self.set_waypoints_calls = []

    def set_waypoints(self, route_waypoints, altitude_m=None, strategy=None):
        self.set_waypoints_calls.append((route_waypoints, altitude_m, strategy))
        return {
            "current_gps": {"lat": 52.0, "lon": 21.0, "alt": 15.0},
        }


class TestWaypointDroneTools(unittest.TestCase):
    def test_safety_supervisor_checks_on_each_observation_cadence(self):
        supervisor = FlightSafetySupervisor(None, None, None, None)

        self.assertEqual(supervisor.check_interval_s, 0.5)

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
        with patch("builtins.print") as mock_print:
            tool_result = tool.invoke(
                {
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
                f"Strategy: {strategy}",
                "Waypoints:",
                "1. x=0.1, y=0.2 — enter open space",
            ],
        )
        self.assertIn("Route submitted", tool_result)
        self.assertNotIn("Executed GPS coordinate array", tool_result)
        self.assertNotIn("52.0", tool_result)

    def test_set_waypoints_rejects_empty_route(self):
        tool = create_set_waypoints(FakeRosBridge())

        with self.assertRaises(ValueError):
            tool.invoke({"strategy": "No safe route is currently visible.", "waypoints": []})

    def test_set_waypoints_schema_orders_strategy_before_waypoints(self):
        tool_schema = create_set_waypoints(FakeRosBridge()).args_schema.model_json_schema()

        self.assertEqual(
            list(tool_schema["properties"]),
            ["strategy", "waypoints", "altitude_m"],
        )
        self.assertEqual(tool_schema["required"], ["strategy", "waypoints"])
        self.assertIn("Summarize accumulated observations", tool_schema["description"])
        self.assertIn(
            "First summarize mission-relevant evidence",
            tool_schema["properties"]["strategy"]["description"],
        )
        waypoint_schema = tool_schema["$defs"]["RouteWaypoint"]
        self.assertEqual(list(waypoint_schema["properties"]), ["x", "y", "purpose"])
        self.assertEqual(waypoint_schema["required"], ["x", "y"])


class TestWaypointDroneMapUtils(unittest.TestCase):
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
    def test_get_observation_waits_for_first_message(self):
        bridge = DroneRosBridge.__new__(DroneRosBridge)
        bridge.latest_observation = DroneObservation()
        bridge._has_observation = False
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
            bridge = DroneRosBridge()

        waypoints = [{"x": 0.25, "y": 0.75}]

        submission_result = bridge.set_waypoints(
            waypoints,
            altitude_m=18.0,
            strategy="Survey the nearest roof.",
        )

        self.assertEqual(submission_result["status"], "submitted")
        self.assertEqual(len(published), 1)
        command_payload = json.loads(published[0].data)
        self.assertEqual(command_payload["waypoints"], waypoints)
        self.assertEqual(command_payload["altitude_m"], 18.0)
        self.assertEqual(command_payload["strategy"], "Survey the nearest roof.")


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
            ros_bridge.get_observation.return_value = DroneObservation(
                front_image_b64="front-b64",
                map_image_b64="map-b64",
                gps={"lat": 52.0, "lon": 21.0, "alt": 20.0},
                height_m=20.0,
            )
            mission_agent = WaypointDroneAgent(
                model="fake-model",
                tools=[],
                name="Mission Agent",
                ros_bridge=ros_bridge,
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
        self.assertIn("BLUE = remaining future route", text)
        self.assertNotIn("Map width:", text)
        self.assertNotIn("Current GPS/location", text)
        self.assertIn("Height: 20.0 m", text)
        self.assertNotIn("Route state:", text)
        self.assertNotIn("Pose:", text)
        self.assertNotIn("Route status:", text)
        self.assertIn("Inspect the open road.", text)
        self.assertIn("data:image/jpeg;base64,front-b64", image_urls)
        self.assertIn("data:image/jpeg;base64,map-b64", image_urls)
        trace_config = llm.invoke.call_args.kwargs["config"]
        self.assertEqual(trace_config["run_name"], "Mission Agent")
        self.assertEqual(trace_config["tags"], ["agent:Mission Agent"])
        self.assertEqual(trace_config["metadata"]["agent_name"], "Mission Agent")

    def test_safety_checker_keeps_only_current_observation(self):
        with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
            llm = MagicMock()
            mock_llm_factory.return_value.bind_tools.return_value = llm
            llm.invoke.return_value = self._response()

            from robocrew.robots.WaypointDrone.waypoint_drone_agent import WaypointDroneAgent

            safety_agent = WaypointDroneAgent(
                model="fake-model",
                tools=[],
                name="Safety Checker",
                is_safety_checker=True,
                history_len=8,
            )
            common_observation = {
                "map_image_b64": "map-b64",
                "gps": {"lat": 52.0, "lon": 21.0},
                "height_m": 20.0,
                "route_state": "executing",
            }

            safety_agent.process_observation(
                DroneObservation(front_image_b64="old-front", **common_observation)
            )
            safety_agent.process_observation(
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
        self.assertEqual(llm.invoke.call_args.kwargs["config"]["run_name"], "Safety Checker")


if __name__ == "__main__":
    unittest.main()
