
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from tools import finish_task
from LLMAgent import LLMAgent
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))
from connectors.XLeRobot.tools import move_forward, turn  # type: ignore[import]

print("Starting agent initialization...")


prompt = "You are mobile household robot with two arms. Remember to write your reasoning before using tools to justify your actions."
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    system_prompt=prompt,
    tools=[
        move_forward,
        turn,
        finish_task,
    ],
    main_camera_usb_port="/dev/camera_center",
    history_len=4,
    sounddevice_index=2,
)

print("Agent initialized.")
result = agent.go()
print(result)
