from os import getenv
from robocrew.core.tools import create_say, remember_thing, recall_thing
from dotenv import find_dotenv, load_dotenv
import time
import base64
from robocrew.core.lidar import init_lidar, run_scanner
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model
import queue
load_dotenv(find_dotenv())


base_system_prompt = """
## ROBOT SPECS
- Mobile household robot with two arms

## NAVIGATION RULES
- Check angle grid at top of image - target must be within ±15° of center before moving forward
- Watch for obstacles in your path - if obstacle blocks the way, navigate around it first
- Never call move_forward 3+ times if nothing changes
- If target is off-center: use turn_left or turn_right to align BEFORE moving forward
- Reference floor meters only if floor visible and scale not on objects
- Watch for obstacles between you and target - plan path to avoid them
"""

class LLMAgent():
    def __init__(
            self,
            model: str,
            tools: list,
            main_camera,
            name: str | None = None,
            system_prompt: str | None = None,
            thinking_level: str | None = None,
            camera_fov: int = 90,
            sounddevice_index_or_alias=None,
            servo_controler=None,
            wakeword: str = "robot",
            tts: bool = False,
            history_len: int | None = None,
            use_memory: bool = False,
            lidar_usb_port: str | None = None,
        ):
        """
        model: name of the model to use (e.g. 'google_genai:gemini-3.1-pro-preview').
        tools: list of langchain tools.
        main_camera: robot front camera object.
        name: optional agent name shown in logs (e.g. 'Planner', 'Controller').
        system_prompt: custom system prompt - optional.
        thinking_level: Gemini 3.x thinking effort level. Options: 'minimal', 'low', 'medium', 'high'.
            Gemini 3.1 Pro supports 'low' and 'high' only. Gemini 3 Flash supports all four levels.
        camera_fov: field of view (degrees) of the main camera.
        sounddevice_index_or_alias: sounddevice index or alias of the microphone for voice input.
        wakeword: wakeword that triggers the robot to accept a new task.
        history_len: number of newest request-response pairs to keep in context.
        use_memory: set to True to enable long-term memory (requires sqlite3).
        tts: set to True to enable text-to-speech.
        lidar_usb_port: USB port of the LiDAR sensor for navigation support.
        """
        system_prompt = system_prompt or base_system_prompt
        self.name = name
        
        if use_memory:
            
            tools.append(remember_thing)
            tools.append(recall_thing)
            memory_prompt = (
                " You have a memory. When you find important things (like a specific room, object, or person) "
                "or complete a navigation step, use the `remember_thing` tool to save it for later. "
                "Do not wait for the user to tell you to remember. Be proactive."
            )
            system_prompt += memory_prompt

        self.tts = tts
        #self.sound_receiver = None

        self.task = None
        
        self.sounddevice_index_or_alias = sounddevice_index_or_alias
        if self.sounddevice_index_or_alias is not None:
            from robocrew.core.sound_receiver import SoundReceiver
            self.task_queue = queue.Queue()
            self.sound_receiver = SoundReceiver(self.sounddevice_index_or_alias, self.task_queue, wakeword)
            
        self.navigation_mode = "normal"  # or "precision"

        # Add TTS tool if enabled (after sound_receiver is created so we can pass it)
        if tts:
            say_tool = create_say(getattr(self, 'sound_receiver', None))
            tools.append(say_tool)
            tts_prompt = (
                " You can speak to the user using the `say` tool. "
                "Use it to communicate important updates, greet users, or answer their questions verbally."
            )
            system_prompt += tts_prompt


        model_kwargs = {}
        if thinking_level is not None:
            model_kwargs["generation_config"] = {"thinking_config": {"thinking_level": thinking_level.upper()}}

        llm = init_chat_model(model, model_kwargs=model_kwargs or None)
        #llm = init_chat_model(model="google/gemini-3-flash-preview", model_provider="openai", base_url="https://openrouter.ai/api/v1", api_key=getenv("OPENROUTER_API_KEY"))
        self.llm = llm.bind_tools(tools)#, parallel_tool_calls=False)
        self.tools = tools
        self.tool_name_to_tool = {tool.name: tool for tool in self.tools}
        self.system_message = SystemMessage(content=system_prompt)
        self.message_history = [self.system_message]
        self.history_len = history_len
        # cameras
        self.main_camera = main_camera
        self.camera_fov = camera_fov
        self.servo_controler = servo_controler

        # lidar
        self.lidar = None
        self.lidar_bg = None
        self.lidar_scale = None
        
        if lidar_usb_port:
            self.lidar, self.lidar_bg, self.lidar_scale = init_lidar(lidar_usb_port)
        if self.servo_controler and self.servo_controler.left_arm_head_usb:
            self.servo_controler.reset_head_position()

    def invoke_tool(self, tool_call):
        # convert string to real function
        requested_tool = self.tool_name_to_tool[tool_call["name"]]
        args = tool_call["args"]
        tool_output = requested_tool.invoke(args)
        # f aitional output is present
        if isinstance(tool_output, tuple) and len(tool_output) == 2:
            additional_output = HumanMessage(content=tool_output[1])
            tool_output = tool_output[0]
        else:
            additional_output = None
        return ToolMessage(tool_output, tool_call_id=tool_call["id"]), additional_output
    
    def cut_off_context(self, nr_of_loops):
        """
        Trims the message history in the state to keep only the most recent context for the agent.
        """        
        ai_indices = [i for i, msg in enumerate(self.message_history) if msg.type == "human"]
        if len(ai_indices) >= nr_of_loops:
            start_index = ai_indices[-nr_of_loops]
            self.message_history = [self.system_message] + self.message_history[start_index:]

    def check_for_new_task(self):
        """Non-blockingly checks the queue for a new task."""
        if self.sounddevice_index_or_alias and not self.task_queue.empty():
            self.task = self.task_queue.get()
            
    def lidar_content(self, content):
        lidar_buf, lidar_front_dist = run_scanner(self.lidar, self.lidar_bg, self.lidar_scale, flip_x=True)
        lidar_image_base64 = base64.b64encode(lidar_buf.getvalue()).decode('utf-8')
        
        content.extend([{
            "type": "text", 
            "text": f"""\n\nLiDAR Sensor: Distance from your front edge to nearest obstacle in front: {lidar_front_dist:.1f} cm.
            
Remember that lidar scans only in one horizontal plane (0.5m high), so obstacles above or below that plane may not be detected.
            """
        },
        {"type": "text", "text": "\n\nLiDAR Map (Top-down view, obstacles are marked in red):"},
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{lidar_image_base64}"}
        }])
        return content

    def fetch_camera_images_base64(self):
        for attempt in range(3):
            try:
                image_bytes = self.main_camera.capture_image(
                    camera_fov=self.camera_fov,
                    navigation_mode=self.navigation_mode,
                )
                return [base64.b64encode(image_bytes).decode('utf-8')]
            except RuntimeError as exc:
                print(f"Camera capture failed (attempt {attempt + 1}/3): {exc}")
                # Camera can be briefly unavailable after manipulation tools release/reacquire it.
                time.sleep(0.3 * (attempt + 1))
                self.main_camera.reopen()
        raise RuntimeError("Failed to fetch camera image after retries.")
    
    def main_loop_content(self):
        try:
            camera_images = self.fetch_camera_images_base64()
        except RuntimeError as exc:
            print(f"Skipping this loop because camera is unavailable: {exc}")
            time.sleep(0.5)
            return
        
        content=[
                {"type": "text", "text": "Main camera view:"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{camera_images[0]}"}
                },
                {"type": "text", "text": f"\n\nYour task is: '{self.task}'"}
        ]
        
        if self.lidar:
            content = self.lidar_content(content)
        message = HumanMessage(content)
        
        self.message_history.append(message)
        response = self.llm.invoke(self.message_history)
        print(response.content)
        reasoning_tokens = response.usage_metadata.get('output_token_details', {}).get('reasoning', 0)
        if reasoning_tokens:
            print(f"[thinking: {reasoning_tokens} tokens]")
        for tool_call in response.tool_calls:
                    print(f"Calling {tool_call['name']} with {tool_call['args']} args")
        
        
        self.message_history.append(response)
        if self.history_len:
            self.cut_off_context(self.history_len)
        # execute tool
        for tool_call in response.tool_calls:
            tool_response, additional_response = self.invoke_tool(tool_call)
            self.message_history.append(tool_response)
            if additional_response:
                self.message_history.append(additional_response)
            if tool_call["name"] == "go_to_precision_mode":
                self.navigation_mode = "precision"
            elif tool_call["name"] == "go_to_normal_mode":
                self.navigation_mode = "normal"
            if tool_call["name"] == "finish_task":
                report = tool_call["args"].get("report", "Task finished")
                self.task = None
                print(f"Task finished: {report}")
                return report

    def go(self):
        try:
            while True:
                if self.task:
                    self.main_loop_content()
                else:
                    # idle mode
                    time.sleep(0.5)
                    
                if self.sounddevice_index_or_alias:
                    self.check_for_new_task()

        except KeyboardInterrupt:
            print("Interrupted by user, shutting down.")

        finally:
            if self.servo_controler:
                print("Disconnecting servo controller...")
                self.servo_controler.disconnect()