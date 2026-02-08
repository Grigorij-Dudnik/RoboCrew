"""
Earth Rover basic movement example demonstrating essential navigation capabilities.
"""

from robocrew.robots.EarthRover.Earth_Rover_LLM_agent import EarthRoverAgent
from robocrew.robots.EarthRover.tools import \
    move_forward, \
    move_backward, \
    move_forward_max_speed, \
    turn_right_forward_rotation, \
    turn_left_forward_rotation, \
    turn_right_backward_rotation, \
    turn_left_backward_rotation

# init Earth Rover agent
agent = EarthRoverAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[
        move_forward,
        move_backward,
        move_forward_max_speed,
        turn_right_forward_rotation,
        turn_left_forward_rotation,
        turn_right_backward_rotation,
        turn_left_backward_rotation,
    ],
    history_len=4,
    camera_fov=120,
    use_location_visualizer=True,
)
agent.waypoints = [
    (50.46199017312358, 18.52245882339651), 
    (50.46312884434534, 18.519863268946846),
    (50.46416841170328, 18.52073741261176),
    (50.46931451571181, 18.515441379426754),
    (50.47290427097344, 18.51146549840186),
    (50.47523116115213, 18.50625015824145),
    ]

agent.go()
