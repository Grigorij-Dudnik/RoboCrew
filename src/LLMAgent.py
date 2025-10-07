from smolagents import ToolCallingAgent, LiteLLMModel, TransformersModel

#from phoenix.otel import register
from dotenv import find_dotenv, load_dotenv
from time import perf_counter
from pydantic_ai import Agent, BinaryContent
import cv2

from haystack import Pipeline
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage, ByteStream, ImageContent
import base64


load_dotenv(find_dotenv())
from langfuse import get_client
langfuse = get_client()



dotenv_time = perf_counter()
# langfuse or arize
# register()
Agent.instrument_all()


tool_calling_agent_system_prompt = "You are mobile robot with two arms."



class LLMAgent():
    def __init__(self, model, tools, system_prompt=None, main_camera_usb_port=None):
        system_prompt = system_prompt or tool_calling_agent_system_prompt
        #super().__init__(model=model, tools=tools, system_prompt=system_prompt)
        self.message_history = []
        # cameras
        self.main_camera = cv2.VideoCapture(main_camera_usb_port) if main_camera_usb_port else None

        self.generator = OpenAIChatGenerator(model="gpt-4o-mini")

    def capture_image(self):
        _, frame = self.main_camera.read()
        _, buffer = cv2.imencode('.jpg', frame)
        image_bytes = buffer.tobytes()
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        return base64_image

    def go(self):
        while True:
            if self.main_camera:
                base64_image = self.capture_image()
                image_content = ImageContent(
                    base64_image=base64_image,
                    mime_type="image/jpeg",
                    detail="low"
                )
                message = ChatMessage.from_user(
                    text="Here is the current view from your main camera. Tell what you can see here",
                    meta={
                        "images": [image_content]
                    }
                )
            else:
                message = ChatMessage.from_user("What is your next action?")
            self.message_history.append(message)
            response = self.generator.run(messages=self.message_history)
            reply = response["replies"][0]
            self.message_history.append(reply)
            print(reply._content)

if __name__ == "__main__":

    def do_nothing():
        print("Doing nothing...")
        return "Doing nothing."
    agent = LLMAgent(
        model="openai:gpt-4.1-nano",
        tools=[
            do_nothing,
        ]
    )
    result = agent.go()
    print(result)