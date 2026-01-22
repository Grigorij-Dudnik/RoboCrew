from robocrew.core.LLMAgent import LLMAgent
from langchain_core.messages import HumanMessage, SystemMessage
import os

class XLeRobotAgent(LLMAgent):
	"""XLeRobot specific LLM agent that inherits from base LLMAgent."""
	def __init__(
		self,
		model,
		tools,
		system_prompt=None,
		camera_fov=90,
		history_len=None,
		use_memory=False,
		main_camera=None,
		sounddevice_index=None,
		servo_controler=None,
		wakeword=None,
		tts=False,
		lidar_usb_port=None,
	):
		# Use XLeRobot specific system prompt if none provided
		if system_prompt is None:
			prompt_path = os.path.join(os.path.dirname(__file__), "xlerobot.prompt")
			with open(prompt_path, "r", encoding="utf-8") as f:
				xlerobot_system_prompt = f.read()
		else:
			xlerobot_system_prompt = system_prompt

		super().__init__(
			model=model,
			tools=tools,
			main_camera=main_camera,
			system_prompt=xlerobot_system_prompt,
			camera_fov=camera_fov,
			sounddevice_index=sounddevice_index,
			servo_controler=servo_controler,
			wakeword=wakeword,
			tts=tts,
			history_len=history_len,
			use_memory=use_memory,
			lidar_usb_port=lidar_usb_port
		)

	# No new features or methods; inherits all behavior from LLMAgent
