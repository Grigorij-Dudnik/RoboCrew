"""
Earth Rover basic movement example demonstrating essential navigation capabilities.
"""

from robocrew.robots.EarthRover.Earth_Rover_LLM_agent import EarthRoverAgent
from robocrew.robots.EarthRover.tools import \
    move_forward, \
    move_backward, \
    turn_right, \
    turn_left, \
    go_forward_with_turning_right, \
    go_forward_with_turning_left

# init Earth Rover agent with SDK URL
agent = EarthRoverAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[
        move_forward,
        move_backward,
        turn_left,
        turn_right,
        go_forward_with_turning_right,
        go_forward_with_turning_left,
    ],
    history_len=8,              # nr of last message-answer pairs to keep
    camera_fov=90,
)

agent.task = "Go forward for 3 meters, and then turn right in endless."

agent.go()
