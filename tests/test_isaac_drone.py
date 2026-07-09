import os
import json
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))
sys.modules.setdefault("pygame", MagicMock())

import langchain.chat_models

setattr(langchain.chat_models, "init_chat_model", MagicMock())

from robocrew.robots.IsaacDrone.bridge import IsaacDroneObservation, IsaacDroneRosBridge
from robocrew.robots.IsaacDrone.tools import create_set_waypoints


class FakeDrone:
    def __init__(self):
        self.calls = []

    def set_waypoints(self, waypoints, altitude_m=None, note=None):
        self.calls.append((waypoints, altitude_m, note))
        return {
            "current_gps": {"lat": 52.0, "lon": 21.0, "alt": 15.0},
        }


class TestIsaacDroneTools(unittest.TestCase):
    def test_set_waypoints_accepts_arbitrary_non_empty_route(self):
        drone = FakeDrone()
        tool = create_set_waypoints(drone)
        waypoints = [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}, {"x": 0.5, "y": 0.6}]

        result = tool.invoke({"waypoints": waypoints, "altitude_m": 22.0, "note": "inspect roofs"})

        self.assertEqual(drone.calls, [(waypoints, 22.0, "inspect roofs")])
        self.assertIn("Route submitted", result)
        self.assertIn("Current drone GPS/location", result)
        self.assertNotIn("Executed GPS coordinate array", result)
        self.assertIn("52.0", result)

    def test_set_waypoints_rejects_empty_route(self):
        tool = create_set_waypoints(FakeDrone())

        with self.assertRaises(ValueError):
            tool.invoke({"waypoints": []})


class TestIsaacDroneBridge(unittest.TestCase):
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
            bridge = IsaacDroneRosBridge()

        waypoints = [{"x": 0.25, "y": 0.75}]

        result = bridge.set_waypoints(waypoints, altitude_m=18.0, note="survey")

        self.assertEqual(result["status"], "submitted")
        self.assertEqual(len(published), 1)
        payload = json.loads(published[0].data)
        self.assertEqual(payload["waypoints"], waypoints)
        self.assertEqual(payload["altitude_m"], 18.0)
        self.assertEqual(payload["note"], "survey")


class TestIsaacDroneAgent(unittest.TestCase):
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

            from robocrew.robots.IsaacDrone.isaac_drone_agent import IsaacDroneAgent

            drone = MagicMock()
            drone.get_observation.return_value = IsaacDroneObservation(
                front_image_b64="front-b64",
                map_image_b64="map-b64",
                gps={"lat": 52.0, "lon": 21.0, "alt": 20.0},
                height_m=20.0,
            )
            agent = IsaacDroneAgent(model="fake-model", tools=[], drone=drone)
            agent.task = "Inspect the open road."

            agent.main_loop_content()

        human_messages = [m for m in agent.message_history if getattr(m, "type", None) == "human"]
        content = human_messages[0].content
        text = "\n".join(item["text"] for item in content if item["type"] == "text")
        image_urls = [item["image_url"]["url"] for item in content if item["type"] == "image_url"]
        self.assertIn("Front camera view", text)
        self.assertIn("Map view", text)
        self.assertIn("Current GPS/location", text)
        self.assertIn("Height: 20.0 m", text)
        self.assertNotIn("Pose:", text)
        self.assertNotIn("Route status:", text)
        self.assertIn("Inspect the open road.", text)
        self.assertIn("data:image/jpeg;base64,front-b64", image_urls)
        self.assertIn("data:image/jpeg;base64,map-b64", image_urls)


if __name__ == "__main__":
    unittest.main()
