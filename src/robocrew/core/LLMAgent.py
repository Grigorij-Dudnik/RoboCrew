from robocrew.core.utils import capture_image
from robocrew.core.sound_receiver import SoundReceiver
from dotenv import find_dotenv, load_dotenv
import cv2
import base64
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model
import queue
load_dotenv(find_dotenv())


base_system_prompt = """You are a mobile household robot with two arms. Your arms are VERY SHORT (only ~30cm reach).

CRITICAL MANIPULATION RULES:
- Your arms can ONLY reach objects that are DIRECTLY IN FRONT of you and VERY CLOSE (within 30cm).
- If the object you want to grab/interact with, you are TOO FAR. Keep approaching.
- Only attempt to grab/interact with the object when it dominates your view and is centered.
- Using a tool does not guarantee success. Remember to verify if item was picked up successfully. If not - repeat.

NAVIGATION AND OBSTACLE RULES:
- When you enter a new area or cannot see your target, use look_around FIRST to scan the environment. 
look_around gives you a panoramic view of your surroundings - use it to locate objects, people, and obstacles before moving.
- After look_around, you will know where things are and can navigate directly instead of wandering blindly.
- If your view shows a wall, obstacle, or blocked path STOP moving forward.
- When you see a wall or obstacle close ahead: FIRST use turn_left or turn_right to face a clear direction, THEN move forward.
- If you moved forward but the view hasn't changed (still seeing the same wall/obstacle) or changed an angle instead of distance, you are STUCK.
- When STUCK: move backward (forward by negative distance), then use turn_left or turn_right by 90+ degrees to face a completely different direction before moving forward again.
- NEVER call move_forward more than 2 times in a row if you keep seeing the same obstacle.
- If you have object you want to go in the your view, but not in front of you - turn in the direction of the object by calculating an angle from the grid drawen in top edge of the image.

DECISION PRIORITY:
1. Am I stuck/hitting a wall? → Go backward and turn first
2. Do I know where the target is? → If NO, use look_around to scan the environment
3. Can I see the target, but it not in front of me? → Turn towards it using angle drawen on the photo.
4. Do I have target in front of me? -> Navigate toward it.
5. Is the target close enough (touching bottom edge of view)? → Use manipulation tool
6. Target not visible after scanning? → Move to a new location and look_around again
"""

class LLMAgent():
    def __init__(self, model, tools, main_camera, system_prompt=None, camera_fov=120, sounddevice_index=None, wakeword="robot", tts=False, history_len=None, debug_mode=False, use_memory=False):
        """
        model: name of the model to use
        tools: list of langchain tools
        system_prompt: custom system prompt - optional
        main_camera: provide your robot front camera object if you want to use it.
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
        self.llm = llm.bind_tools(tools, parallel_tool_calls=False)
        self.tools = tools
        self.tool_name_to_tool = {tool.name: tool for tool in self.tools}
        self.system_message = SystemMessage(content=system_prompt)
        self.message_history = [self.system_message]
        self.history_len = history_len
        # cameras
        self.main_camera = main_camera
        self.main_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.camera_fov = camera_fov


    def invoke_tool(self, tool_call):
        # convert string to real function
        requested_tool = self.tool_name_to_tool[tool_call["name"]]
        args = tool_call["args"]
        tool_output = requested_tool.invoke(args)
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
            image_bytes = capture_image(self.main_camera, camera_fov=self.camera_fov)
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
                if tool_call["name"] == "finish_task":
                    print("Task finished, going idle.")
                    return "Task finished, going idle."
                
            if self.sounddevice_index:
                self.check_for_new_task()
            
