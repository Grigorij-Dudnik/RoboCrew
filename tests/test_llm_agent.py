import os
import sys
import queue
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage


# ---------------------------------------------------------------------------
# Helper: build a minimal LLMAgent without real hardware or LLM API calls
# ---------------------------------------------------------------------------

def make_agent():
    """
    Construct an LLMAgent with all hardware and LLM calls mocked out.
    - init_chat_model is patched so no API key is needed.
    - main_camera is a MagicMock (never used in unit tests).
    - No sound device, no TTS, no LiDAR, no servo.
    """
    with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
        # init_chat_model(model) -> llm; llm.bind_tools(tools) -> bound_llm
        mock_llm_factory.return_value.bind_tools.return_value = MagicMock()
        from robocrew.core.LLMAgent import LLMAgent
        agent = LLMAgent(
            model="fake-model",
            tools=[],
            main_camera=MagicMock(),
            sounddevice_index_or_alias=None,
            tts=False,
            lidar_usb_port=None,
            servo_controler=None,
        )
    return agent


# ---------------------------------------------------------------------------
# cut_off_context
# ---------------------------------------------------------------------------

class TestCutOffContext(unittest.TestCase):

    def _build_history(self, agent, n_pairs):
        """Append n_pairs of (HumanMessage, AI mock) to the agent's history."""
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
        human_msgs = [
            m for m in agent.message_history
            if hasattr(m, "type") and m.type == "human"
        ]
        self.assertEqual(len(human_msgs), 2)

    def test_keeps_last_messages_not_first(self):
        """After trimming, the remaining human messages should be the most recent ones."""
        agent = make_agent()
        self._build_history(agent, 5)
        agent.cut_off_context(2)
        human_msgs = [
            m for m in agent.message_history
            if hasattr(m, "type") and m.type == "human"
        ]
        # Last two messages added were "human message 3" and "human message 4"
        self.assertIn("3", human_msgs[0].content)
        self.assertIn("4", human_msgs[1].content)

    def test_no_trim_when_history_shorter_than_n(self):
        """If there are fewer human messages than nr_of_loops, nothing is trimmed."""
        agent = make_agent()
        self._build_history(agent, 2)
        original_len = len(agent.message_history)
        agent.cut_off_context(5)  # keep 5, only have 2
        self.assertEqual(len(agent.message_history), original_len)

    def test_no_trim_when_history_exactly_n(self):
        agent = make_agent()
        self._build_history(agent, 3)
        original_len = len(agent.message_history)
        agent.cut_off_context(3)
        self.assertEqual(len(agent.message_history), original_len)

    def test_single_message_kept_with_n_equals_1(self):
        agent = make_agent()
        self._build_history(agent, 5)
        agent.cut_off_context(1)
        human_msgs = [
            m for m in agent.message_history
            if hasattr(m, "type") and m.type == "human"
        ]
        self.assertEqual(len(human_msgs), 1)
        self.assertIn("4", human_msgs[0].content)  # last one


# ---------------------------------------------------------------------------
# check_for_new_task
# ---------------------------------------------------------------------------

class TestCheckForNewTask(unittest.TestCase):

    def test_picks_up_task_from_non_empty_queue(self):
        agent = make_agent()
        agent.sounddevice_index_or_alias = True  # truthy — enables queue check
        agent.task_queue = queue.Queue()
        agent.task_queue.put("Go to the kitchen")
        agent.check_for_new_task()
        self.assertEqual(agent.task, "Go to the kitchen")

    def test_task_unchanged_when_queue_empty(self):
        agent = make_agent()
        agent.sounddevice_index_or_alias = True
        agent.task_queue = queue.Queue()
        agent.task = None
        agent.check_for_new_task()
        self.assertIsNone(agent.task)

    def test_does_not_check_queue_when_no_sound_device(self):
        """With sounddevice_index_or_alias=None the queue must not be consumed."""
        agent = make_agent()
        # sounddevice_index_or_alias is already None from make_agent()
        agent.task_queue = queue.Queue()
        agent.task_queue.put("Should not be picked up")
        agent.task = None
        agent.check_for_new_task()
        self.assertIsNone(agent.task)

    def test_only_one_task_consumed_per_call(self):
        """A single call must dequeue at most one task."""
        agent = make_agent()
        agent.sounddevice_index_or_alias = True
        agent.task_queue = queue.Queue()
        agent.task_queue.put("Task 1")
        agent.task_queue.put("Task 2")
        agent.check_for_new_task()
        self.assertEqual(agent.task, "Task 1")
        self.assertEqual(agent.task_queue.qsize(), 1)  # Task 2 still waiting


# ---------------------------------------------------------------------------
# invoke_tool
# ---------------------------------------------------------------------------

class TestInvokeTool(unittest.TestCase):

    def _make_mock_tool(self, name, return_value):
        t = MagicMock()
        t.name = name
        t.invoke.return_value = return_value
        return t

    def test_returns_tool_message(self):
        agent = make_agent()
        mock_tool = self._make_mock_tool("my_tool", "tool result")
        agent.tool_name_to_tool = {"my_tool": mock_tool}
        tool_call = {"name": "my_tool", "args": {}, "id": "call_1"}
        tool_msg, additional = agent.invoke_tool(tool_call)
        self.assertIsInstance(tool_msg, ToolMessage)

    def test_tool_message_contains_output(self):
        agent = make_agent()
        mock_tool = self._make_mock_tool("my_tool", "navigation complete")
        agent.tool_name_to_tool = {"my_tool": mock_tool}
        tool_call = {"name": "my_tool", "args": {}, "id": "call_2"}
        tool_msg, _ = agent.invoke_tool(tool_call)
        self.assertIn("navigation complete", str(tool_msg.content))

    def test_passes_args_to_tool(self):
        agent = make_agent()
        mock_tool = self._make_mock_tool("move_tool", "moved")
        agent.tool_name_to_tool = {"move_tool": mock_tool}
        tool_call = {"name": "move_tool", "args": {"distance_meters": 1.5}, "id": "call_3"}
        agent.invoke_tool(tool_call)
        mock_tool.invoke.assert_called_once_with({"distance_meters": 1.5})

    def test_additional_output_is_none_for_plain_string_result(self):
        agent = make_agent()
        mock_tool = self._make_mock_tool("plain_tool", "just a string")
        agent.tool_name_to_tool = {"plain_tool": mock_tool}
        _, additional = agent.invoke_tool({"name": "plain_tool", "args": {}, "id": "c1"})
        self.assertIsNone(additional)

    def test_additional_output_returned_for_tuple_result(self):
        """Tools returning (str, content_list) — e.g. look_around — must
        produce a HumanMessage as additional output."""
        agent = make_agent()
        image_content = [{"type": "text", "text": "Left view"}, {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}]
        mock_tool = self._make_mock_tool("look_around", ("Looked around", image_content))
        agent.tool_name_to_tool = {"look_around": mock_tool}
        tool_msg, additional = agent.invoke_tool({"name": "look_around", "args": {}, "id": "c2"})
        self.assertIsNotNone(additional)
        self.assertIsInstance(additional, HumanMessage)

    def test_tool_message_content_is_primary_output_from_tuple(self):
        """When tool returns a tuple, the ToolMessage content must be the first element."""
        agent = make_agent()
        mock_tool = self._make_mock_tool("look_around", ("Looked around", []))
        agent.tool_name_to_tool = {"look_around": mock_tool}
        tool_msg, _ = agent.invoke_tool({"name": "look_around", "args": {}, "id": "c3"})
        self.assertEqual(tool_msg.content, "Looked around")


if __name__ == "__main__":
    unittest.main()
