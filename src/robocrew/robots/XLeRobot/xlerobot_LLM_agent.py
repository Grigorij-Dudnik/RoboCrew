from robocrew.core.LLMAgent import LLMAgent
from langchain_core.messages import HumanMessage, SystemMessage
import os

class XLeRobotAgent(LLMAgent):
	"""XLeRobot specific LLM agent that inherits from base LLMAgent."""
	def __init__(
		self,
		model: str,
		tools: list,
		name: str | None = None,
		system_prompt: str | None = None,
		thinking_level: str | None = None,
		camera_fov: int = 90,
		history_len: int | None = None,
		use_memory: bool = False,
		main_camera=None,
		sounddevice_index_or_alias=None,
		servo_controler=None,
		wakeword: str | None = None,
		tts: bool = False,
		lidar_usb_port: str | None = None,
	):

		super().__init__(
			model=model,
			tools=tools,
			main_camera=main_camera,
			name=name,
			system_prompt=system_prompt,
			thinking_level=thinking_level,
			camera_fov=camera_fov,
			sounddevice_index_or_alias=sounddevice_index_or_alias,
			servo_controler=servo_controler,
			wakeword=wakeword,
			tts=tts,
			history_len=history_len,
			use_memory=use_memory,
			lidar_usb_port=lidar_usb_port
		)

	# No new features or methods; inherits all behavior from LLMAgent
