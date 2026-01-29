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

# init Earth Rover agent
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
    history_len=8,
    camera_fov=90,
)
agent.target_coordinates = 50.26689081583593, 18.705729346165146

agent.task = "Try to reach the target"

agent.go()
