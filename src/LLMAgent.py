from utils import horizontal_angle_grid
from dotenv import find_dotenv, load_dotenv
from time import perf_counter
import cv2
import base64
import sys
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model
from sound_receiver import SoundReceiver
import threading
import queue
load_dotenv(find_dotenv())


class LLMAgent():
    def __init__(self, model, tools, system_prompt=None, main_camera_usb_port=None, camera_fov=120, sounddevice_index=None, wakeword="robot", history_len=None):
        """
        model: name of the model to use
        tools: list of langchain tools
        system_prompt: custom system prompt - optional
        main_camera_usb_port: provide usb port of your robot front camera if you want to use it.
        camera_fov: field of view (degrees) of your main camera.
        sounddevice_index: provide sounddevice index of your microphone if you want robot to hear.
        wakeword: custom wakeword hearing which robot will set your sentence as a task o do.
        history_len: if you want agent to have messages history cuttof, provide number of newest request-response pairs to keep.
        """
        base_system_prompt = "You are mobile robot with two arms."
        self.task = "You are standing in a room. Explore the environment, find a backpack and approach it."
        system_prompt = system_prompt or base_system_prompt
        llm = init_chat_model(model)
        self.llm = llm.bind_tools(tools, parallel_tool_calls=False)
        self.tools = tools
        self.system_message = SystemMessage(content=system_prompt)
        self.message_history = [self.system_message]
        # cameras
        self.main_camera = cv2.VideoCapture(main_camera_usb_port) if main_camera_usb_port else None
        self.hitory_len = history_len
        if self.main_camera:
            self.main_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.camera_fov = camera_fov
        self.sounddevice_index = sounddevice_index
        if self.sounddevice_index:
            self.task_queue = queue.Queue()
            self.sound_receiver = SoundReceiver(sounddevice_index, self.task_queue, wakeword)
            # self.task = ""

    def capture_image(self):
        self.main_camera.grab() # Clear the buffer
        _, frame = self.main_camera.read()
        frame = horizontal_angle_grid(frame, h_fov=self.camera_fov)
        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

    def invoke_tool(self, tool_call):
        # convert string to real function
        tool_name_to_tool = {tool.name: tool for tool in self.tools}
        name = tool_call["name"]
        requested_tool = tool_name_to_tool[name]
        args = tool_call["args"]
        tool_output = requested_tool.invoke(args)
        return ToolMessage(tool_output, tool_call_id=tool_call["id"])
    
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
            if self.main_camera:
                print("Capturing image from main camera...")
                image_bytes = self.capture_image()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                print("Image captured and encoded.")
                
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
            else:
                message = HumanMessage(content=f"Your task is: '{self.task}'")


                
            self.message_history.append(message)
            response = self.llm.invoke(self.message_history)
            print(response)
            #print(response.tool_calls)
            self.message_history.append(response)
            if self.hitory_len:
                self.cut_off_context(self.hitory_len)

            # execute tool
            for tool_call in response.tool_calls:
                tool_response = self.invoke_tool(tool_call)
                self.message_history.append(tool_response)
                if tool_call["name"] == "finish_task":
                    return "Task finished, going idle."
                
            if self.sounddevice_index:
                self.check_for_new_task()
            

if __name__ == "__main__":

    @tool
    def do_nothing() -> str:
        """does nothing at all"""
        print("Doing nothing...")
        return "Doing nothing."
    
    agent = LLMAgent(
        model="google_genai:gemini-robotics-er-1.5-preview",
        tools=[
            do_nothing,
        ],
    )
    result = agent.go()
    print(result)
