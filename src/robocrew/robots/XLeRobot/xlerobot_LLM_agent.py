from robocrew.core.LLMAgent import LLMAgent, base_system_prompt
from robocrew.core.tools import create_say
from robocrew.core.lidar import init_lidar, run_scanner
import base64
import queue

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
		self.sounddevice_index_or_alias = sounddevice_index_or_alias
		self.sound_receiver = None
		self.speech_queue = None
		self.user_text = None
		self.lidar = self.lidar_bg = self.lidar_scale = self.latest_lidar_b64 = None

		if self.sounddevice_index_or_alias is not None:
			# import here to avoid importing sounddevice and its dependencies when not needed
			from robocrew.core.sound_receiver import SoundReceiver
			self.speech_queue = queue.Queue()
			self.sound_receiver = SoundReceiver(
				self.sounddevice_index_or_alias,
				self.speech_queue,
				wakeword,
			)
		if lidar_usb_port:
			self.lidar, self.lidar_bg, self.lidar_scale = init_lidar(lidar_usb_port)

		if tts:
			tools.append(create_say(self.sound_receiver))
			system_prompt = (system_prompt or base_system_prompt) + (
				" You can speak to the user using the `say` tool. "
				"Use it to communicate important updates, greet users, or answer their questions verbally."
			)

		super().__init__(
			model=model,
			tools=tools,
			main_camera=main_camera,
			name=name,
			system_prompt=system_prompt,
			thinking_level=thinking_level,
			camera_fov=camera_fov,
			servo_controler=servo_controler,
			history_len=history_len,
			use_memory=use_memory
		)

	def check_for_new_speech(self):
		"""Non-blockingly checks the speech queue for one heard utterance."""
		if self.sounddevice_index_or_alias and self.speech_queue and not self.speech_queue.empty():
			return self.speech_queue.get()
		return None

	def extra_loop_content(self):
		content = []
		if self.lidar:
			lidar_buf, lidar_front_dist = run_scanner(self.lidar, self.lidar_bg, self.lidar_scale, flip_x=True)
			self.latest_lidar_b64 = base64.b64encode(lidar_buf.getvalue()).decode('utf-8')
			content.extend([
				{"type": "text", "text": f"\n\nLiDAR Sensor: Distance from your front edge to nearest obstacle in front: {lidar_front_dist:.1f} cm.\nRemember that lidar scans only in one horizontal plane (0.5m high), so obstacles above or below that plane may not be detected."},
				{"type": "text", "text": "\n\nLiDAR Map (Top-down view, obstacles are marked in red):"},
				{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{self.latest_lidar_b64}"}},
			])
		if self.sounddevice_index_or_alias and self.user_text:
			content.append({"type": "text", "text": f"\n\nUser said: '{self.user_text}'"})
			self.user_text = None
		return content

	def check_for_new_input(self):
		user_text = self.check_for_new_speech()
		if user_text:
			self.user_text = user_text
			return True
		return False
