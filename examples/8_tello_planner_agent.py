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
    create_save_artifact_photo,
    create_strafe_left,
    create_strafe_right,
    create_takeoff,
    create_turn_left,
    create_turn_right,
)


prompt_dir = Path(__file__).parent.parent.resolve() / "src/robocrew/robots/Tello"
controller_prompt = (
    (prompt_dir / "tello.prompt").read_text(encoding="utf-8")
    + "\n\n"
    + (prompt_dir / "tello_flat_inspection.prompt").read_text(encoding="utf-8")
    + "\n\nWhen working under a planner, finish_task means the current subtask is done. Do not land after a subtask unless the planner asks you to land or you cannot continue safely."
)

tello = Tello()
tello.connect()
print(f"Tello battery: {tello.get_battery()}%")

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
        create_save_artifact_photo(tello),
        create_land(tello),
        finish_task,
    ],
    tello=tello,
    system_prompt=controller_prompt,
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
    "Navigate around the flat. Track which areas are explored and unexplored. "
    "Explore every wall of the flat no farther than 1 meter from the front wall when safe. "
    "Inspect each wall at low, middle, and high flight heights; the flat height is 2.2 meters. "
    "Find artifacts left after renovation. Artifacts are things on the walls that should not be there "
    "(holes, marks, paint gaps, scratches, missing paint, etc.). "
    "For each artifact, fly close enough to center it "
    "in the photo, save an artifact photo, and track what was saved. "
    "After exploring the whole flat, return to the helipad."
)

planner.go()
