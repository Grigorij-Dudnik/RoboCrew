
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from tools import move_forward, turn_right, turn_left
from LLMAgent import LLMAgent

print("Starting agent initialization...")


prompt = "You are mobile household robot with two arms. Your task is to find and approach a human."
agent = LLMAgent(
    model="openai:gpt-4.1-nano",
    system_prompt=prompt,
    tools=[
        move_forward,
        turn_right,
        turn_left,
    ],
    main_camera_usb_port="/dev/video2" 
)

print("Agent initialized.")
result = agent.go()
print(result)
