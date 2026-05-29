import os
import sys
import unittest
import io
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))


def make_xlerobot_agent(**kwargs):
    with patch("robocrew.core.LLMAgent.init_chat_model") as mock_llm_factory:
        mock_llm_factory.return_value.bind_tools.return_value = MagicMock()
        from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent

        return XLeRobotAgent(
            model="fake-model",
            tools=[],
            main_camera=MagicMock(),
            servo_controler=None,
            **kwargs,
        )


class TestXLeRobotListening(unittest.TestCase):

    def test_queued_speech_runs_main_loop_with_user_text(self):
        with patch("robocrew.core.sound_receiver.SoundReceiver"):
            agent = make_xlerobot_agent(sounddevice_index_or_alias="mic_main", wakeword="Bob")

        agent.speech_queue.put("Bob what do you see?")
        agent.fetch_camera_images_base64 = MagicMock(return_value=["image-b64"])
        response = MagicMock()
        response.content = "Hello"
        response.tool_calls = []
        response.usage_metadata = {}
        agent.llm.invoke.return_value = response

        self.assertTrue(agent.check_for_new_input())
        agent.idle = False
        agent.main_loop_content()

        human_messages = [m for m in agent.message_history if getattr(m, "type", None) == "human"]
        self.assertIn({"type": "text", "text": "\n\nUser said: 'Bob what do you see?'"}, human_messages[0].content)
        self.assertTrue(agent.idle)

    def test_queued_speech_continues_without_using_transcript_as_task(self):
        with patch("robocrew.core.sound_receiver.SoundReceiver"):
            agent = make_xlerobot_agent(sounddevice_index_or_alias="mic_main", wakeword="Bob")

        agent.speech_queue.put("Bob bring me a tissue")
        agent.fetch_camera_images_base64 = MagicMock(return_value=["image-b64"])
        response = MagicMock()
        response.content = "Hello"
        response.tool_calls = []
        response.usage_metadata = {}
        agent.llm.invoke.return_value = response

        self.assertTrue(agent.check_for_new_input())
        agent.idle = False
        agent.main_loop_content()

        self.assertNotEqual(agent.task, "Bob bring me a tissue")

    def test_explicit_task_runs_without_microphone(self):
        agent = make_xlerobot_agent()
        agent.task = "Go to the kitchen"
        agent.fetch_camera_images_base64 = MagicMock(return_value=["image-b64"])
        response = MagicMock()
        response.content = "Hello"
        response.tool_calls = []
        response.usage_metadata = {}
        agent.llm.invoke.return_value = response

        agent.idle = False
        agent.main_loop_content()

        human_messages = [m for m in agent.message_history if getattr(m, "type", None) == "human"]
        self.assertIn({"type": "text", "text": "\n\nYour task is: 'Go to the kitchen'"}, human_messages[0].content)

    def test_tts_adds_say_tool_with_sound_receiver(self):
        receiver = MagicMock()
        with patch("robocrew.core.sound_receiver.SoundReceiver", return_value=receiver):
            agent = make_xlerobot_agent(
                sounddevice_index_or_alias="mic_main",
                wakeword="Bob",
                tts=True,
            )

        say_tool = agent.tool_name_to_tool["say"]
        with patch("robocrew.core.tools.speak_and_play"):
            say_tool.invoke({"query": "Hello"})

        receiver.stop_listening.assert_called_once()
        receiver.start_listening.assert_called_once()

    def test_lidar_content_is_xlerobot_specific(self):
        with patch("robocrew.robots.XLeRobot.xlerobot_LLM_agent.init_lidar", return_value=("lidar", "bg", "scale")):
            agent = make_xlerobot_agent(lidar_usb_port="/dev/lidar")

        with patch("robocrew.robots.XLeRobot.xlerobot_LLM_agent.run_scanner", return_value=(io.BytesIO(b"lidar"), 42.0)):
            content = agent.extra_loop_content()

        self.assertIn("42.0 cm", content[0]["text"])
        self.assertEqual(agent.latest_lidar_b64, "bGlkYXI=")


if __name__ == "__main__":
    unittest.main()
