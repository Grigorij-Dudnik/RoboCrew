
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from tools import move_forward, turn_right, turn_left, stop
from LLMAgent import LLMAgent

print("Starting agent initialization...")


prompt = "You are mobile household robot with two arms. Your task is to find exit of the room."
agent = LLMAgent(
    model="openai:gpt-4.1-nano",
    system_prompt=prompt,
    tools=[
        move_forward,
        turn_right,
        turn_left,
        stop
    ],
    main_camera_usb_port="/dev/video2" 
)

print("Agent initialized.")
result = agent.go()
print(result)
