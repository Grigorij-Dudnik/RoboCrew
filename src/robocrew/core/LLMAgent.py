from robocrew.core.utils import capture_image
from robocrew.core.sound_receiver import SoundReceiver
from robocrew.core.tools import create_say
from dotenv import find_dotenv, load_dotenv
import base64
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model
import queue
load_dotenv(find_dotenv())


base_system_prompt_gemini_robotics = """
## ROBOT SPECS
- Mobile household robot with two arms
- ARM REACH: ~30cm only (VERY SHORT)
- Navigation modes: NORMAL (long-distance, forward camera) and PRECISION (close-range, downward camera)

## MANIPULATION RULES - CRITICAL
- ALWAYS switch to PRECISION mode BEFORE any manipulation attempt
- GREEN LINES show your arm reach boundary (only visible in PRECISION mode)
- ONLY manipulate when the BASE of target object is BELOW the green line
- If target is above green line: TOO FAR - move closer first using small forward steps (0.1m)
- Target must be CENTERED in view (middle of image) before grabbing
- If off-center: strafe or turn to align first
- Always verify success after using a tool - retry if failed

## NAVIGATION RULES
- Can't see target? Use look_around FIRST (don't wander blindly)
- Check angle grid at top of image - target must be within ±15° of center before moving forward
- Watch for obstacles in your path - if obstacle blocks the way, navigate around it first
- STUCK (standing on same place after moving)? Switch to PRECISION, use move_backward or strafe
- Never call move_forward 3+ times if nothing changes

## NORMAL MODE (Long-distance)
- Use for: navigation 0.5-3m, exploring
- If target is off-center: use turn_left or turn_right to align BEFORE moving forward
- Before EVERY move_forward: verify target is centered (±15° on angle grid)
- Reference floor meters only if floor visible and scale not on objects
- Watch for obstacles between you and target - plan path to avoid them
- Switch to PRECISION ONLY when target is at the VERY BOTTOM of camera view (almost touching bottom edge)

## PRECISION MODE (Close-range)
- Enter when: target is at very bottom of view (intersectgs with view bottom edge), stuck, or about to manipulate
- You will see: your arms, black basket (your body), and green reach lines
- Small movements only: 0.1-0.3m
- Green lines show arm reach - check if BASE of target is below green line before manipulating
- If target above green line: move forward 0.1m increments until base crosses below line
- Strafe more effective than turn for small adjustments (your body is wide). Combine both starfing and turning to have best results.
- Exit when: far from obstacles/target, or lost target - switch to NORMAL and look_around

## OPERATION SEQUENCE
1. Don't know where target is? → look_around
2. Target visible but far? → NORMAL mode, turn to center it, move_forward
3. Target at bottom of view? → Switch to PRECISION mode
4. In PRECISION, target off-center? → Strafe to center it
5. In PRECISION, target above green line? → Move forward until below line
6. Target centered AND below green line? → Use manipulation tool
7. Stuck or lost target? → PRECISION mode + move_backward/strafe OR switch to NORMAL + look_around
"""

base_system_prompt = """
## ROBOT SPECS
- Mobile household robot with two arms
- ARM REACH: ~30cm only (VERY SHORT)
- Navigation modes: NORMAL (long-distance, forward camera) and PRECISION (close-range, downward camera)

## MANIPULATION RULES - CRITICAL
- ALWAYS switch to PRECISION mode BEFORE any manipulation attempt
- GREEN LINES show your arm reach boundary (only visible in PRECISION mode)
- ONLY manipulate when the BASE of target object is BELOW the green line
- If target is above green line: TOO FAR - move closer first using small forward steps (0.1m)
- Target must be CENTERED in view (middle of image) before grabbing
- If off-center: strafe or turn to align first
- Always verify success after using a tool - retry if failed

## NAVIGATION RULES
- Can't see target? Use look_around FIRST (don't wander blindly)
- Check angle grid at top of image - target must be within ±15° of center before moving forward
- Watch for obstacles in your path - if obstacle blocks the way, navigate around it first
- STUCK (standing on same place after moving)? Switch to PRECISION, use move_backward or strafe
- Never call move_forward 3+ times if nothing changes

## NORMAL MODE (Long-distance)
- Use for: navigation 0.5-3m, exploring
- If target is off-center: use turn_left or turn_right to align BEFORE moving forward
- Before EVERY move_forward: verify target is centered (±15° on angle grid)
- Reference floor meters only if floor visible and scale not on objects
- Watch for obstacles between you and target - plan path to avoid them
- Switch to PRECISION ONLY when target is at the VERY BOTTOM of camera view (almost touching bottom edge)

## PRECISION MODE (Close-range)
- Enter when: target is at very bottom of view (intersectgs with view bottom edge), stuck, or about to manipulate
- You will see: your arms, black basket (your body), and green reach lines
- Small movements only: 0.1-0.3m
- Green lines show arm reach - check if BASE of target is below green line before manipulating
- If target above green line: move forward 0.1m increments until base crosses below line
- Strafe more effective than turn for small adjustments (your body is wide). Combine both starfing and turning to have best results.
- Exit when: far from obstacles/target, or lost target - switch to NORMAL and look_around

## OPERATION SEQUENCE
1. Don't know where target is? → look_around
2. Target visible but far? → NORMAL mode, turn to center it, move_forward
3. Target at bottom of view? → Switch to PRECISION mode
4. In PRECISION, target off-center? → Strafe to center it
5. In PRECISION, target above green line? → Move forward until below line
6. Target centered AND below green line? → Use manipulation tool
7. Stuck or lost target? → PRECISION mode + move_backward/strafe OR switch to NORMAL + look_around
"""

class LLMAgent():
    def __init__(self, model, tools, main_camera, system_prompt=None, camera_fov=90, sounddevice_index=None, servo_controler=None, wakeword="robot", tts=False, history_len=None, debug_mode=False, use_memory=False):
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
        self.servo_controler = servo_controler


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
                
                message = HumanMessage(
                    content=[
                        {"type": "text", "text": "Main camera view:"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
                        },
                        {"type": "text", "text": f"\n\nYour task is: '{self.task}'"}
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
        except KeyboardInterrupt:
            print("Interrupted by user, shutting down.")
        finally:
            if self.servo_controler:
                print("Disconnecting servo controller...")
                self.servo_controler.__del__()