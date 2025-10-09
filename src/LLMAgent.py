#from phoenix.otel import register
from utils import horizontal_angle_grid
from dotenv import find_dotenv, load_dotenv
from time import perf_counter
import cv2
import base64
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.chat_models import init_chat_model


load_dotenv(find_dotenv())


class LLMAgent():
    def __init__(self, model, tools, system_prompt=None, main_camera_usb_port=None, history_len=None):
        base_system_prompt = "You are mobile robot with two arms."
        self.task = "Find where is room exit and exit the room."
        system_prompt = system_prompt or base_system_prompt
        llm = init_chat_model(model)
        self.llm = llm.bind_tools(tools, parallel_tool_calls=False)
        self.tools = tools
        self.message_history = [SystemMessage(content=system_prompt)]
        # cameras
        self.main_camera = cv2.VideoCapture(main_camera_usb_port) if main_camera_usb_port else None
        self.hitory_len = history_len
        if self.main_camera:
            self.main_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    def capture_image(self):
        _, frame = self.main_camera.read()
        frame = horizontal_angle_grid(frame, h_fov=118)
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
    
    def cut_off_context(self, nr_of_messages):
        """
        Trims the message history in the state to keep only the most recent context for the agent.
        """
        if len(self.message_history) <= nr_of_messages:
            return
        
        last_messages = self.message_history[-nr_of_messages:]
        # Find the index of the first 'ai' message from the end in the last nr_of_messages messages
        ai_message_index_in_last_msgs = next(
            (i for i, message in enumerate(last_messages) if message.type == "ai"), None
        )
        # Calculate the actual index of the 'ai' message in the original list
        ai_message_index = len(self.message_history) - nr_of_messages + ai_message_index_in_last_msgs
        # Collect all messages starting from the 'ai' message
        last_messages_excluding_system = [
            msg for msg in self.message_history[ai_message_index:] if msg.type != "system"
        ]
        system_message = self.message_history[0]
        self.message_history = [system_message] + last_messages_excluding_system


    def go(self):
        while True:
            if self.main_camera:
                image_bytes = self.capture_image()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
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
                message = HumanMessage(content="What is your next action?")


                
            self.message_history.append(message)
            response = self.llm.invoke(self.message_history)
            print(response.content)
            print(response.tool_calls)
            self.message_history.append(response)
            if self.hitory_len:
                self.cut_off_context(self.hitory_len)

            # execute tool
            for tool_call in response.tool_calls:
                tool_response = self.invoke_tool(tool_call)
                self.message_history.append(tool_response)
                if tool_call["name"] == "finish_task":
                    return "Task finished, going idle."
            

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
