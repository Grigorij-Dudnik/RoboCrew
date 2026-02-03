"""
Earth Rover basic movement example demonstrating essential navigation capabilities.
"""

from robocrew.robots.EarthRover.Earth_Rover_LLM_agent import EarthRoverAgent
from robocrew.robots.EarthRover.tools import \
    move_forward, \
    move_backward, \
    turn_right, \
    turn_left, \
    move_forward_carefully

# init Earth Rover agent
agent = EarthRoverAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[
        move_forward,
        move_forward_carefully,
        move_backward,
        turn_left,
        turn_right,
    ],
    history_len=7,
    camera_fov=120,
    use_location_visualizer=True,
)
agent.target_coordinates = 50.259180770932396, 18.623472664570965

agent.task = "Follow the target. Direction to target marked with yellow arrow on the map."

agent.go()
