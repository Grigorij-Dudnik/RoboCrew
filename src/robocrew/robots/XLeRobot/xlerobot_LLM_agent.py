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
		tts=False
	):
		"""
		Initialize XLeRobot LLM agent with XLeRobot prompt.
		Args:
			model: name of the model to use
			tools: list of langchain tools
			system_prompt: custom system prompt - optional (uses XLeRobot default if None)
			camera_fov: field of view (degrees) of your main camera
			history_len: if you want agent to have messages history cutoff
			use_memory: set to True to enable long-term memory
			main_camera: provide your robot front camera object
			sounddevice_index: provide sounddevice index of your microphone if you want robot to hear
			servo_controler: servo controller for robot movement
			wakeword: custom wakeword for task setting
			tts: enable text-to-speech
		"""
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
			use_memory=use_memory
		)

	# No new features or methods; inherits all behavior from LLMAgent
