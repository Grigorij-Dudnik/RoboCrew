import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from langchain_core.messages import HumanMessage, ToolMessage


def make_agent(name=None):
    with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
        mock_llm_factory.return_value.bind_tools.return_value = MagicMock()
        from robocrew.core.LLMAgent import LLMAgent

        return LLMAgent(
            model="fake-model",
            tools=[],
            main_camera=MagicMock(),
            name=name,
            servo_controler=None,
        )


class TestCutOffContext(unittest.TestCase):

    def _build_history(self, agent, n_pairs):
        for i in range(n_pairs):
            agent.message_history.append(HumanMessage(content=f"human message {i}"))
            ai_msg = MagicMock()
            ai_msg.type = "ai"
            agent.message_history.append(ai_msg)

    def test_system_message_always_first_after_trim(self):
        agent = make_agent()
        self._build_history(agent, 5)
        agent.cut_off_context(2)
        self.assertEqual(agent.message_history[0], agent.system_message)
        self.assertEqual(agent.message_history[0].type, "system")

    def test_trims_to_last_n_human_messages(self):
        agent = make_agent()
        self._build_history(agent, 5)
        agent.cut_off_context(2)
        human_msgs = [m for m in agent.message_history if getattr(m, "type", None) == "human"]
        self.assertEqual(len(human_msgs), 2)

    def test_keeps_last_messages_not_first(self):
        agent = make_agent()
        self._build_history(agent, 5)
        agent.cut_off_context(2)
        human_msgs = [m for m in agent.message_history if getattr(m, "type", None) == "human"]
        self.assertIn("3", human_msgs[0].content)
        self.assertIn("4", human_msgs[1].content)


class TestMainLoopContent(unittest.TestCase):

    def _response(self):
        response = MagicMock()
        response.content = "Hello"
        response.tool_calls = []
        response.usage_metadata = {}
        return response

    def test_adds_extra_loop_content(self):
        agent = make_agent()
        agent.fetch_camera_images_base64 = MagicMock(return_value=["image-b64"])
        agent.extra_loop_content = MagicMock(return_value=[{"type": "text", "text": "\n\nExtra context"}])
        agent.llm.invoke.return_value = self._response()

        agent.main_loop_content()

        human_messages = [m for m in agent.message_history if getattr(m, "type", None) == "human"]
        self.assertIn({"type": "text", "text": "\n\nExtra context"}, human_messages[0].content)

    def test_main_loop_uses_explicit_task(self):
        agent = make_agent()
        agent.task = "Go to the kitchen"
        agent.fetch_camera_images_base64 = MagicMock(return_value=["image-b64"])
        agent.llm.invoke.return_value = self._response()

        agent.main_loop_content()

        human_messages = [m for m in agent.message_history if getattr(m, "type", None) == "human"]
        self.assertIn({"type": "text", "text": "\n\nYour task is: 'Go to the kitchen'"}, human_messages[0].content)

    def test_silent_tool_hides_call_arguments(self):
        agent = make_agent()
        quiet_tool = MagicMock()
        quiet_tool.name = "quiet_tool"
        quiet_tool.extras = {"silent": True}
        agent.tool_name_to_tool = {"quiet_tool": quiet_tool}
        agent.execute_tool_calls = MagicMock()
        response = self._response()
        response.tool_calls = [
            {"name": "quiet_tool", "args": {"secret": "long value"}, "id": "quiet-call"}
        ]
        agent.llm.invoke.return_value = response

        with patch("builtins.print") as mock_print:
            agent.invoke_llm_with_message(HumanMessage(content="Run quietly"))

        printed = [call.args[0] for call in mock_print.call_args_list]
        self.assertNotIn("Calling quiet_tool with {'secret': 'long value'} args", printed)


class TestInvokeTool(unittest.TestCase):

    def _make_mock_tool(self, name, return_value):
        tool = MagicMock()
        tool.name = name
        tool.invoke.return_value = return_value
        return tool

    def test_returns_tool_message(self):
        agent = make_agent()
        mock_tool = self._make_mock_tool("my_tool", "tool result")
        agent.tool_name_to_tool = {"my_tool": mock_tool}
        tool_msg, _ = agent.invoke_tool({"name": "my_tool", "args": {}, "id": "call_1"})
        self.assertIsInstance(tool_msg, ToolMessage)

    def test_passes_args_to_tool(self):
        agent = make_agent()
        mock_tool = self._make_mock_tool("move_tool", "moved")
        agent.tool_name_to_tool = {"move_tool": mock_tool}
        agent.invoke_tool({"name": "move_tool", "args": {"distance_meters": 1.5}, "id": "call_3"})
        mock_tool.invoke.assert_called_once_with({"distance_meters": 1.5})

    def test_additional_output_returned_for_tuple_result(self):
        agent = make_agent()
        image_content = [{"type": "text", "text": "Left view"}]
        mock_tool = self._make_mock_tool("look_around", ("Looked around", image_content))
        agent.tool_name_to_tool = {"look_around": mock_tool}
        _, additional = agent.invoke_tool({"name": "look_around", "args": {}, "id": "c2"})
        self.assertIsNotNone(additional)
        self.assertIsInstance(additional, HumanMessage)

    def test_named_agent_labels_tool_trace(self):
        agent = make_agent(name="Mission Agent")
        mock_tool = self._make_mock_tool("move_tool", "moved")
        agent.tool_name_to_tool = {"move_tool": mock_tool}

        agent.invoke_tool({"name": "move_tool", "args": {"distance_meters": 1.5}, "id": "call_4"})

        trace_config = mock_tool.invoke.call_args.kwargs["config"]
        self.assertEqual(trace_config["run_name"], "Mission Agent / move_tool")
        self.assertEqual(trace_config["tags"], ["agent:Mission Agent"])
        self.assertEqual(trace_config["metadata"]["agent_name"], "Mission Agent")


if __name__ == "__main__":
    unittest.main()
