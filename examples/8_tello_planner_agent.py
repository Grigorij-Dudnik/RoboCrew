"""
Tello planner + controller example for flat inspection.
"""

from pathlib import Path

from djitellopy import Tello
from robocrew.core.tools import (
    create_execute_subtask,
    finish_task,
)
from robocrew.robots.Tello.tello_LLM_agent import TelloAgent
from robocrew.robots.Tello.tools import (
    create_land,
    create_move_down,
    create_move_forward,
    create_move_up,
    create_strafe_left,
    create_strafe_right,
    create_takeoff,
    create_turn_left,
    create_turn_right,
)


prompt_dir = Path(__file__).parent.parent.resolve() / "src/robocrew/robots/Tello"

tello = Tello()
tello.connect()

controller = TelloAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    tools=[
        create_takeoff(tello),
        create_move_forward(tello),
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
    history_len=30,
)

planner = TelloAgent(
    model="google_genai:gemini-3.1-pro-preview",
    tools=[
        create_execute_subtask(controller),
        finish_task,
    ],
    tello=tello,
    system_prompt=(prompt_dir / "tello_planner.prompt").read_text(encoding="utf-8"),
    history_len=20,
)

planner.task = (
    "Inspect the flat for renovation artifacts on walls. "
    "Save close, centered photos of found artifacts. "
    "After exploring the whole flat, return to the helipad."
)

planner.go()
