"""
This example demonstrates how to use a GR00T N1.6 policy for single-arm manipulation on XLeRobot.

The groot_single_arm_manipulation tool connects to a GR00T policy server over ZeroMQ,
reads camera frames and joint states, and streams actions to the arm in real time.

Before running this example:
  1. Train or download a GR00T model fine-tuned for your task.
  2. Launch the GR00T policy server on a machine with a GPU:
       python gr00t/eval/run_gr00t_server.py \\
           --model-path /path/to/your/finetuned/model \\
           --embodiment-tag NEW_EMBODIMENT \\
           --host 0.0.0.0 \\
           --port 5555
  3. Make sure the server is reachable from the robot.
"""

from pathlib import Path

from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.robots.XLeRobot.tools import (
    create_groot_single_arm_manipulation,
    create_go_to_precision_mode,
    create_go_to_normal_mode,
    create_move_backward,
    create_move_forward,
    create_strafe_right,
    create_strafe_left,
    create_look_around,
    create_turn_right,
    create_turn_left,
)
from robocrew.robots.XLeRobot.servo_controls import ServoControler


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
prompt_path = Path(__file__).parent.parent.resolve() / "src/robocrew/robots/XLeRobot/xlerobot.prompt"
with open(prompt_path, "r") as f:
    system_prompt = f.read()

# ---------------------------------------------------------------------------
# Hardware setup
# ---------------------------------------------------------------------------
main_camera = RobotCamera("/dev/camera_center")

right_arm_wheel_usb = "/dev/arm_right"
left_arm_head_usb  = "/dev/arm_left"
servo_controler = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

# ---------------------------------------------------------------------------
# Movement tools
# ---------------------------------------------------------------------------
move_forward  = create_move_forward(servo_controler)
move_backward = create_move_backward(servo_controler)
turn_left     = create_turn_left(servo_controler)
turn_right    = create_turn_right(servo_controler)
strafe_left   = create_strafe_left(servo_controler)
strafe_right  = create_strafe_right(servo_controler)

look_around        = create_look_around(servo_controler, main_camera)
go_to_precision_mode = create_go_to_precision_mode(servo_controler)
go_to_normal_mode    = create_go_to_normal_mode(servo_controler)

# ---------------------------------------------------------------------------
# GR00T manipulation tool
#
# Requires a running GR00T policy server (see instructions at top of file).
# Motor IDs must match the order used during data collection:
#   [shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]
# ---------------------------------------------------------------------------
collect_tissue = create_groot_single_arm_manipulation(
    tool_name="Collect_tissue",
    tool_description=(
        "Use this tool to pick up a tissue and throw it to the bin using the robot arm. "
        "Only call this tool when you are very close to the tissue and looking straight at it."
    ),
    task_prompt="Collect tissue to the bin.",
    server_host="100.85.166.124",  
    server_port=5555,
    arm_port=right_arm_wheel_usb,
    motor_ids=[1, 2, 3, 4, 5, 6],
    camera1_index_or_path="/dev/camera_center",
    camera2_index_or_path="/dev/camera_right",  # overview camera
    camera_width=640,
    camera_height=480,
    main_camera_object=main_camera,
    servo_controller=servo_controler,
    execution_time=30,
    fps=25,
    timeout_ms=15000,
)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = XLeRobotAgent(
    model="google_genai:gemini-3-flash-preview",
    system_prompt=system_prompt,
    tools=[
        move_forward,
        move_backward,
        strafe_left,
        strafe_right,
        turn_left,
        turn_right,
        look_around,
        collect_tissue,
        go_to_precision_mode,
        go_to_normal_mode,
    ],
    history_len=8,
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
)

agent.task = "Do nothing else but just call collect tissue tool. No matter if you see any tissue or not."

agent.go()
