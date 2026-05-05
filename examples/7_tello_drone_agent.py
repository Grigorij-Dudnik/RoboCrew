"""
Tello drone example demonstrating basic LLM-controlled flight.
"""

from djitellopy import Tello
from robocrew.core.tools import finish_task
from robocrew.robots.Tello.tello_LLM_agent import TelloAgent
from robocrew.robots.Tello.tools import (
    create_land,
    create_move_backward,
    create_move_down,
    create_move_forward,
    create_move_up,
    create_strafe_left,
    create_strafe_right,
    create_takeoff,
    create_turn_left,
    create_turn_right,
)


tello = Tello()
tello.connect()

agent = TelloAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    tools=[
        create_takeoff(tello),
        create_move_forward(tello),
        create_move_backward(tello),
        create_move_up(tello),
        create_move_down(tello),
        create_strafe_left(tello),
        create_strafe_right(tello),
        create_turn_left(tello),
        create_turn_right(tello),
        create_land(tello),
        finish_task,
    ],
    tello=tello,
    skills=["flat_inspection"],
)

agent.task = (
    "Inspect all walls of my house. Find artifacts that left after renovation."
)

agent.go()
