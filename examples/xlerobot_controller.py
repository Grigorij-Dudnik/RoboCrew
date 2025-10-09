
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from tools import move_forward, turn_right, turn_left, finish_task
from LLMAgent import LLMAgent

print("Starting agent initialization...")


prompt = "You are mobile household robot with two arms. Remember to write your reasoning before using tools to justify your actions."
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    system_prompt=prompt,
    tools=[
        move_forward,
        turn_right,
        turn_left,
        finish_task,
    ],
    main_camera_usb_port="/dev/video2",
    history_len=4,
)

print("Agent initialized.")
result = agent.go()
print(result)
