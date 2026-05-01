"""
Tello drone example demonstrating basic LLM-controlled flight.
"""

from djitellopy import Tello
from robocrew.core.tools import finish_task
from robocrew.robots.Tello.tello_LLM_agent import TelloAgent
from robocrew.robots.Tello.tools import (
    create_tello_land,
    create_tello_move_forward,
    create_tello_takeoff,
    create_tello_turn_left,
    create_tello_turn_right,
)


tello = Tello()
tello.connect()

agent = TelloAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    tools=[
        create_tello_takeoff(tello),
        create_tello_move_forward(tello),
        create_tello_turn_left(tello),
        create_tello_turn_right(tello),
        create_tello_land(tello),
        finish_task,
    ],
    tello=tello,
)

agent.task = (
    "Take off, move forward 60 centimeters, turn right 90 degrees, "
    "move forward 40 centimeters, then land."
)

agent.go()
