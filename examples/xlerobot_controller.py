
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from tools import move_forward, turn
from LLMAgent import LLMAgent

print("Starting agent initialization...")
agent = LLMAgent(
    model_id="gpt-4.1-nano",
    tools=[
        move_forward,
        turn
    ]
)

print("Agent initialized.")
result = agent.run("Start!")
print(result)
