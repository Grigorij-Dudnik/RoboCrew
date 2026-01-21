from robocrew.core.utils import capture_image
#from robocrew.core.sound_receiver import SoundReceiver
from robocrew.core.tools import create_say
from dotenv import find_dotenv, load_dotenv
import base64
from . import lidar
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
            model,
            tools,
            main_camera,
            system_prompt=None,
            camera_fov=90,
            sounddevice_index=None,
            servo_controler=None,
            wakeword="robot",
            tts=False,
            history_len=None,
            debug_mode=False,
            use_memory=False,
            lidar_usb_port=None,
        ):
        """
        model: name of the model to use
        tools: list of langchain tools
        system_prompt: custom system prompt - optional
        main_camera: provide your robot front camera object.
        camera_fov: field of view (degrees) of your main camera.
        sounddevice_index: provide sounddevice index of your microphone if you want robot to hear.
        wakeword: custom wakeword hearing which robot will set your sentence as a task o do.
        history_len: if you want agent to have messages history cuttof, provide number of newest request-response pairs to keep.
        use_memory: set to True to enable long-term memory (requires sqlite3).
        tts: set to True to enable text-to-speech (robot can speak).
        lidar_usb_port: provide usb port of your lidar if you want robot to support your navigation with lidar.
        """
        system_prompt = system_prompt or base_system_prompt
        
        if use_memory:
            from robocrew.core.tools import remember_thing, recall_thing
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

        self.task = "You are standing in a room. Explore the environment, find a backpack and approach it."
        
        self.sounddevice_index = sounddevice_index
        if self.sounddevice_index is not None:
            self.task_queue = queue.Queue()
            #self.sound_receiver = SoundReceiver(sounddevice_index, self.task_queue, wakeword)
        self.debug = debug_mode
        self.navigation_mode = "normal"  # or "precision"

        # Add TTS tool if enabled (after sound_receiver is created so we can pass it)
        if tts:
            say_tool = create_say(self.sound_receiver)
            tools.append(say_tool)
            tts_prompt = (
                " You can speak to the user using the `say` tool. "
                "Use it to communicate important updates, greet users, or answer their questions verbally."
            )
            system_prompt += tts_prompt


        llm = init_chat_model(model)
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
        if lidar_usb_port:
            self.lidar = lidar.init_lidar(lidar_usb_port)

        #TODO: Tidy this up, propably when we restructure LLMAgent
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
        if not self.task_queue.empty():
            self.task = self.task_queue.get()

    def go(self):
        try:
            while True:
                image_bytes = capture_image(self.main_camera.capture, camera_fov=self.camera_fov, navigation_mode=self.navigation_mode)
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                if self.debug:
                    open(f"debug/latest_view.jpg", "wb").write(image_bytes)
                
                content=[
                    {"type": "text", "text": "Main camera view:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    },
                    {"type": "text", "text": f"\n\nYour task is: '{self.task}'"}
                ]

                if self.lidar:
                    lidar_buf, lidar_front_dist = lidar.run_scanner(self.lidar)
                    lidar_image_base64 = base64.b64encode(lidar_buf.getvalue()).decode('utf-8')
                    
                    content.extend([{
                        "type": "text", 
                        "text": f"\n\nLiDAR Sensor: Distance from your front edge to nearest obstacle in front: {lidar_front_dist:.1f} cm."
                    },
                    {"type": "text", "text": "\n\nLiDAR Map (Top-down view, obstacles are marked in red):"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{lidar_image_base64}"}
                    }])

                message = HumanMessage(content=content)
                
                self.message_history.append(message)
                response = self.llm.invoke(self.message_history)
                print(response.content)
                print(response.tool_calls)
                
                self.message_history.append(response)
                if self.history_len:
                    self.cut_off_context(self.history_len)
                # execute tool
                for tool_call in response.tool_calls:
                    tool_response, additional_response = self.invoke_tool(tool_call)
                    self.message_history.append(tool_response)
                    if additional_response:
                        self.message_history.append(additional_response)
                            # Special handling for save_checkpoint
                    if tool_call["name"] == "save_checkpoint":
                        checkpoint_info = tool_call["args"].get("checkpont_query")
                        self.system_message.content += f"\n[CHECKPOINT DONE] {checkpoint_info}"
                    if tool_call["name"] == "go_to_precision_mode":
                        self.navigation_mode = "precision"
                    elif tool_call["name"] == "go_to_normal_mode":
                        self.navigation_mode = "normal"
                    if tool_call["name"] == "finish_task":
                        print("Task finished, going idle.")
                        return "Task finished, going idle."
                    
                if self.sounddevice_index:
                    self.check_for_new_task()
        except KeyboardInterrupt:
            print("Interrupted by user, shutting down.")
        finally:
            if self.servo_controler:
                print("Disconnecting servo controller...")
                self.servo_controler.disconnect()
            if self.lidar:
                print("Stopping and disconnecting LiDAR...")
                self.lidar.stop()
                self.lidar.disconnect()