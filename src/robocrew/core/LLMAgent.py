from robocrew.core.utils import capture_image
from robocrew.core.sound_receiver import SoundReceiver
from dotenv import find_dotenv, load_dotenv
import cv2
import base64
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model
import queue
load_dotenv(find_dotenv())


base_system_prompt = """
GENERAL SITUATION:
- You are a mobile household robot with two arms. Your arms are VERY SHORT (only ~30cm reach).
- You have access to two movement modes: NORMAL (long-distance moves, camera looks ahead) and PRECISION (short precize moves, camera looks to robot body).

CRITICAL MANIPULATION RULES:
- Activate manipulation tools ONLY when target is close - within 30cm (within green lines).
- Only attempt to grab/interact with the object when it is close enough (base of the target BELOW green line) and DIRECTLY IN FRONT of you (at very middle of the image).
- If target is not in the middle of the image, use strafe or turn tools to align.
- Using a tool does not guarantee success. Remember to verify if item was picked up successfully. If not - repeat.

NAVIGATION AND OBSTACLE RULES:
- When you cannot see your target, use look_around FIRST to scan the environment. 
- After look_around, you will know where things are and can navigate directly instead of wandering blindly.
- ONLY use move_forward when the target is DIRECTLY in front of you (within ±10 degrees of center, check the angle grid at top of image).
- If the target is even slightly to the side (15+ degrees off-center), use turn_left or turn_right FIRST to align before moving.
- If you moved forward but the view hasn't changed (still seeing the same wall/obstacle), you are STUCK.
- If you used "move forward", but in fact you just rotated in the same place without changing position, you are STUCK.
- When STUCK: Go to PRECISION mode. Turning is not effective when STUCK, use move_backward or strafe tools instead.
- NEVER call move_forward more than 2 times in a row if you keep seeing the same obstacle.

NORMAL MODE:
- Use NORMAL MODE for: long-distance navigation (0.5-3 meters), exploring new areas.
- You have meters scale drawn on the floor. Reference it only if floor is visivle, and scale is not drawen on other objects. Othrwice, switch to precision mode.

PRECISION MODE:
- Enter PRECISION MODE only when you are very close to target or obstacles and you can't see the floor in the bootm of the image.
- Arms and black basket are the parts of your body. You can see them in the camera view in precision mode. Take your body into account when choosing tool to maneuver.
- In PRECISION MODE: use SMALL movements only (0.1-0.2 meters for moves or strifes).
- Because your body is wide, using "strafe" is more effective than "turn" in case of small adjustments. 
- Use PRECISION MODE for: final approach to target, maneuvering near obstacles, tight spaces, alignment for manipulation.
- Always switch to PRECISION MODE before attempting any manipulation.
- In precision mode, you have green lines drawen that show range of your arms
- Activate manipulation tools only when target is within range. Othwerwise, move closer first.
- If you lost your target in PRECISION MODE, go back to normal.
- Exit PRECISION MODE when: you are far from obstacles/target (can see floor in camera view). Use NORMAL MODE to look far ahead.
- If in PRECISION MODE you lost your target and don't know where it could be, look around. If it not helps, swith to normal mode to look forward.

DECISION PRIORITY:
1. Am I very close to target/obstacles? → Enter PRECISION MODE (small movements)
2. Am I stuck/hitting a wall? → Enter PRECISION MODE (small movements)
3. Do I know where the target is? → If NO, use look_around
5. Can I see the target but it's not centered (>10° off)? → Turn towards it
6. Is the target directly in front (<10° off-center)? → Move forward (0.1-0.2m in precision mode, 0.3-3m in normal mode)
7. Is the target close enough (below green lines) AND centered? → Use manipulation tool
8. Target not visible after scanning? → Move to new location
"""

class LLMAgent():
    def __init__(self, model, tools, main_camera, system_prompt=None, camera_fov=90, sounddevice_index=None, wakeword="robot", tts=False, history_len=None, debug_mode=False, use_memory=False):
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
        self.sound_receiver = None

        self.task = "You are standing in a room. Explore the environment, find a backpack and approach it."
        
        self.sounddevice_index = sounddevice_index
        if self.sounddevice_index is not None:
            self.task_queue = queue.Queue()
            self.sound_receiver = SoundReceiver(sounddevice_index, self.task_queue, wakeword)
            # self.task = ""
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
        while True:
            image_bytes = capture_image(self.main_camera.capture, camera_fov=self.camera_fov, navigation_mode=self.navigation_mode)
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            if self.debug:
                open(f"debug/latest_view.jpg", "wb").write(image_bytes)
            
            message = HumanMessage(
                content=[
                    {"type": "text", "text": "Here is the current view from your main camera. Use it to understand your current status."},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                    },
                    {"type": "text", "text": f"Your task is: '{self.task}'"}
                ]
            )
               
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
            