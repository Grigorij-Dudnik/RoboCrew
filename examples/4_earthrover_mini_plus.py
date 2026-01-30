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
    history_len=6,
    camera_fov=100,
    use_location_visualizer=True,
)
agent.target_coordinates = 50.30107135941755, 18.6724942284762

agent.task = "Follow the target. Direction to target marked with yellow arrow on map."

agent.go()
