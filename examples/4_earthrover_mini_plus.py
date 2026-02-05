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
    history_len=4,
    camera_fov=120,
    use_location_visualizer=True,
)
agent.waypoints = [
    (50.260504811881184, 18.585664752785213), 
    (50.26067393589781, 18.59067010893742), 
    (50.263471599349636, 18.600700771653397), 
    (50.26275607990065, 18.602425811028276),
    (50.261639047439566, 18.604020186018648),
    (50.25994587473119, 18.609209113928962),
    ]

agent.go()
