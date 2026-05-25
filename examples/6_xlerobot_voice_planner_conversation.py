"""
Voice conversation with a Planner + Executor XLeRobot setup.

The Planner listens after the wakeword, receives what the robot heard together
with fresh camera/sensor context, and decides whether to chat or delegate a
physical subtask to the Executor.
"""

from pathlib import Path

from robocrew.core.camera import RobotCamera
from robocrew.core.tools import create_execute_subtask, finish_task
from robocrew.robots.XLeRobot.servo_controls import ServoControler
from robocrew.robots.XLeRobot.tools import (
    create_go_to_normal_mode,
    create_go_to_precision_mode,
    create_look_around,
    create_move_backward,
    create_move_forward,
    create_strafe_left,
    create_strafe_right,
    create_turn_left,
    create_turn_right,
)
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent


prompt_dir = Path(__file__).parent.parent.resolve() / "src/robocrew/robots/XLeRobot"
controller_prompt = (prompt_dir / "xlerobot.prompt").read_text(encoding="utf-8")
planner_prompt = (prompt_dir / "planner.prompt").read_text(encoding="utf-8")
planner_prompt += """

## VOICE CONVERSATION
- Treat each heard utterance as the active planner mission until you call `finish_task`.
- If information is missing, ask a short question with `say`, then wait for the user.
- If the user is only making casual conversation, answer briefly with `say` and then call `finish_task`.
- If the user requests physical robot work (like moving or grabbing things), use `execute_subtask` to delegate concrete goals to the executor.
- After each executor report, decide the next subtask or call `finish_task` when the user request is satisfied.
"""


main_camera = RobotCamera("/dev/camera_center")

right_arm_wheel_usb = "/dev/arm_right"
left_arm_head_usb = "/dev/arm_left"
servo_controler = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

move_forward = create_move_forward(servo_controler)
move_backward = create_move_backward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)
strafe_left = create_strafe_left(servo_controler)
strafe_right = create_strafe_right(servo_controler)
look_around = create_look_around(servo_controler, main_camera)
go_to_precision_mode = create_go_to_precision_mode(servo_controler)
go_to_normal_mode = create_go_to_normal_mode(servo_controler)

executor = XLeRobotAgent(
    model="google_genai:gemini-robotics-er-1.6-preview",
    thinking_level="high",
    tools=[
        move_forward,
        move_backward,
        strafe_left,
        strafe_right,
        turn_left,
        turn_right,
        look_around,
        go_to_precision_mode,
        go_to_normal_mode,
        finish_task,
    ],
    history_len=8,
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
    system_prompt=controller_prompt,
)

planner = XLeRobotAgent(
    model="google_genai:gemini-3.5-flash",
    thinking_level="high",
    tools=[
        look_around,
        create_execute_subtask(executor),
        finish_task,
    ],
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
    system_prompt=planner_prompt,
    sounddevice_index_or_alias="mic_main",
    lidar_usb_port="/dev/lidar",
    #wakeword="Bob",
    tts=True,
)

print("Listening for conversation after the wakeword...")
planner.go()
