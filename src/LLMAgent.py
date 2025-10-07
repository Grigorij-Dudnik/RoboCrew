from smolagents import ToolCallingAgent, LiteLLMModel, TransformersModel

#from phoenix.otel import register
from dotenv import find_dotenv, load_dotenv
from time import perf_counter
import cv2
import base64
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model


load_dotenv(find_dotenv())





class LLMAgent():
    def __init__(self, model, tools, system_prompt=None, main_camera_usb_port=None):
        base_system_prompt = "You are mobile robot with two arms."
        system_prompt = system_prompt or base_system_prompt
        self.llm = init_chat_model(model)
        self.tools = tools
        self.message_history = [SystemMessage(content=system_prompt)]
        # cameras
        self.main_camera = cv2.VideoCapture(main_camera_usb_port) if main_camera_usb_port else None

    def capture_image(self):
        _, frame = self.main_camera.read()
        _, buffer = cv2.imencode('.jpg', frame)
        return buffer.tobytes()

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
                        }
                    ]
                )
            else:
                message = HumanMessage(content="What is your next action?")
            self.message_history.append(message)
            response = self.llm.invoke(self.message_history, tools=self.tools)
            self.message_history.append(response)
            print(response.content)
            

if __name__ == "__main__":

    def do_nothing():
        print("Doing nothing...")
        return "Doing nothing."
    agent = LLMAgent(
        model="gpt-4.1-nano",
        tools=[
            do_nothing,
        ],
    )
    result = agent.go()
    print(result)