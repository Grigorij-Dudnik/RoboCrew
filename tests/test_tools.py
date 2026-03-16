import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from robocrew.core.tools import finish_task, remember_thing, recall_thing, create_say, create_execute_subtask


# ---------------------------------------------------------------------------
# finish_task
# ---------------------------------------------------------------------------

class TestFinishTask(unittest.TestCase):

    def test_returns_provided_report(self):
        result = finish_task.invoke({"report": "Delivered the package"})
        self.assertEqual(result, "Delivered the package")

    def test_default_report_when_empty(self):
        result = finish_task.invoke({})
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0, "Default report should not be empty")

    def test_report_content_preserved(self):
        msg = "Could not find the target after 3 attempts"
        result = finish_task.invoke({"report": msg})
        self.assertEqual(result, msg)


# ---------------------------------------------------------------------------
# remember_thing / recall_thing  (patch the module-level singleton)
# ---------------------------------------------------------------------------

class TestMemoryTools(unittest.TestCase):

    def test_remember_thing_calls_add_memory_with_correct_text(self):
        with patch("robocrew.core.tools.robot_memory") as mock_mem:
            mock_mem.add_memory.return_value = "Memory added: kitchen on first floor"
            result = remember_thing.invoke({"text": "kitchen on first floor"})
            mock_mem.add_memory.assert_called_once_with("kitchen on first floor")

    def test_remember_thing_returns_memory_confirmation(self):
        with patch("robocrew.core.tools.robot_memory") as mock_mem:
            mock_mem.add_memory.return_value = "Memory added: test"
            result = remember_thing.invoke({"text": "test"})
            self.assertEqual(result, "Memory added: test")

    def test_recall_thing_calls_search_memory_with_query(self):
        with patch("robocrew.core.tools.robot_memory") as mock_mem:
            mock_mem.search_memory.return_value = "Found memories: kitchen on first floor"
            recall_thing.invoke({"query": "kitchen"})
            mock_mem.search_memory.assert_called_once_with("kitchen")

    def test_recall_thing_returns_search_results(self):
        with patch("robocrew.core.tools.robot_memory") as mock_mem:
            mock_mem.search_memory.return_value = "No matching memories found."
            result = recall_thing.invoke({"query": "garage"})
            self.assertEqual(result, "No matching memories found.")

    def test_remember_and_recall_use_same_memory_instance(self):
        """Both tools must operate on robot_memory, not separate instances."""
        with patch("robocrew.core.tools.robot_memory") as mock_mem:
            mock_mem.add_memory.return_value = "ok"
            mock_mem.search_memory.return_value = "found"
            remember_thing.invoke({"text": "bedroom upstairs"})
            recall_thing.invoke({"query": "bedroom"})
            # Both should have hit the same mock object
            mock_mem.add_memory.assert_called_once()
            mock_mem.search_memory.assert_called_once()


# ---------------------------------------------------------------------------
# create_say
# ---------------------------------------------------------------------------

class TestCreateSay(unittest.TestCase):

    def test_say_calls_speak_and_play(self):
        with patch("robocrew.core.tools.speak_and_play") as mock_speak:
            say = create_say(None)
            say.invoke({"query": "Hello, I am your robot"})
            mock_speak.assert_called_once_with("Hello, I am your robot")

    def test_say_with_receiver_stops_and_restarts_listening(self):
        receiver = MagicMock()
        with patch("robocrew.core.tools.speak_and_play"):
            say = create_say(receiver)
            say.invoke({"query": "Moving forward"})
            receiver.stop_listening.assert_called_once()
            receiver.start_listening.assert_called_once()

    def test_say_without_receiver_does_not_crash(self):
        with patch("robocrew.core.tools.speak_and_play"):
            say = create_say(None)
            result = say.invoke({"query": "Test message"})
            self.assertIsNotNone(result)

    def test_say_result_contains_spoken_text(self):
        with patch("robocrew.core.tools.speak_and_play"):
            say = create_say(None)
            result = say.invoke({"query": "I see the table"})
            self.assertIn("I see the table", result)

    def test_stop_listening_called_before_speak(self):
        """Microphone must be muted before TTS starts."""
        receiver = MagicMock()
        call_order = []
        receiver.stop_listening.side_effect = lambda: call_order.append("stop")
        receiver.start_listening.side_effect = lambda: call_order.append("start")

        with patch("robocrew.core.tools.speak_and_play",
                   side_effect=lambda _: call_order.append("speak")):
            say = create_say(receiver)
            say.invoke({"query": "Hello"})

        self.assertEqual(call_order, ["stop", "speak", "start"])


# ---------------------------------------------------------------------------
# create_execute_subtask
# ---------------------------------------------------------------------------

class TestCreateExecuteSubtask(unittest.TestCase):

    def test_sets_executor_task_and_calls_main_loop(self):
        """The tool must assign the subtask and drive the executor loop."""
        mock_executor = MagicMock()
        mock_executor.task = None

        def finish_on_first_call():
            mock_executor.task = None  # loop ends when task is cleared
            return "done"

        mock_executor.main_loop_content.side_effect = finish_on_first_call

        execute_subtask = create_execute_subtask(mock_executor)
        execute_subtask.invoke({"reasoning": "I see the cup", "subtask": "Pick up the cup"})

        mock_executor.main_loop_content.assert_called()

    def test_returns_executor_result(self):
        mock_executor = MagicMock()
        mock_executor.task = None

        def finish_on_first_call():
            mock_executor.task = None
            return "subtask completed successfully"

        mock_executor.main_loop_content.side_effect = finish_on_first_call

        execute_subtask = create_execute_subtask(mock_executor)
        result = execute_subtask.invoke({"reasoning": "plan", "subtask": "go to kitchen"})
        self.assertEqual(result, "subtask completed successfully")


if __name__ == "__main__":
    unittest.main()
