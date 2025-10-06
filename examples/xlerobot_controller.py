
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from tools import move_forward, turn_right, turn_left, stop
from LLMAgent import LLMAgent

print("Starting agent initialization...")

prompt = "You are mobile household robot with two arms. Your task is to move forwar, turn 270 degree, move again. Remember t stop afteral."
agent = LLMAgent(
    model_id="gpt-4.1-nano",
    tools=[
        move_forward,
        turn_right,
        turn_left,
        stop
    ]
)

print("Agent initialized.")
result = agent.run("Start!")
print(result)
