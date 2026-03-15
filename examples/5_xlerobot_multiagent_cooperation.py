"""
This example demonstrates the Planner + Controller architecture for a complex multi-step mission.
The Planner (smart model) decomposes a tissue collection mission into subtasks and delegates them
to the Controller (fast model) which handles navigation and arm manipulation.
"""

from pathlib import Path
from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.camera import RobotCamera
from robocrew.core.tools import finish_task, create_execute_subtask
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.robots.XLeRobot.tools import \
    create_vla_single_arm_manipulation, \
    create_go_to_precision_mode, \
    create_go_to_normal_mode, \
    create_move_backward, \
    create_move_forward, \
    create_strafe_right, \
    create_strafe_left, \
    create_look_around, \
    create_turn_right, \
    create_turn_left
from robocrew.robots.XLeRobot.servo_controls import ServoControler

# load prompts
prompt_dir = Path(__file__).parent.parent.resolve() / "src/robocrew/robots/XLeRobot"

with open(prompt_dir / "xlerobot.prompt", "r") as f:
    controller_prompt = f.read()

with open(prompt_dir / "planner.prompt", "r") as f:
    planner_prompt = f.read()

# set up main camera
main_camera = RobotCamera("/dev/camera_center")

# set up servo controler
right_arm_wheel_usb = "/dev/arm_right"
left_arm_head_usb = "/dev/arm_left"
servo_controler = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

# set up movement tools
move_forward = create_move_forward(servo_controler)
move_backward = create_move_backward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)
strafe_left = create_strafe_left(servo_controler)
strafe_right = create_strafe_right(servo_controler)
look_around = create_look_around(servo_controler, main_camera)
go_to_precision_mode = create_go_to_precision_mode(servo_controler)
go_to_normal_mode = create_go_to_normal_mode(servo_controler)

# set up arm manipulation tools
# remember to run the VLA server before using manipulation tools:
#   python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080

pick_up_tissue = create_vla_single_arm_manipulation(
    tool_name="Pick_up_tissue",
    tool_description="Pick up a tissue from a surface. Use only when very close to the tissue and looking straight at it.",
    task_prompt="Pick up tissue.",
    server_address="greg-pc:8080",
    policy_name="Grigorij/pi05_collect_tissue_23_02",
    policy_type="pi05",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"camera1": {"index_or_path": "/dev/camera_center"}, "camera2": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cuda",
)

throw_to_trash = create_vla_single_arm_manipulation(
    tool_name="Throw_to_trash",
    tool_description="Drop the held object into the trash bin. Use only when very close to the bin and looking straight at it.",
    task_prompt="Drop object into trash bin.",
    server_address="greg-pc:8080",
    policy_name="Grigorij/act_right_arm_give_notebook",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cuda",
    execution_time=45,
)

# init controller agent (fast model, movement + manipulation tools)
executor = XLeRobotAgent(
    model="google_genai:gemini-3-flash-preview",
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
        pick_up_tissue,
        throw_to_trash,
        finish_task,
    ],
    history_len=8,
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
    system_prompt=controller_prompt,
)

# set up planner tools
execute_subtask = create_execute_subtask(executor)

# init planner agent (smart model, subtask delegation)
planner = LLMAgent(
    model="google_genai:gemini-3.1-pro-preview",
    tools=[
        look_around,
        execute_subtask,
        finish_task,
    ],
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
    system_prompt=planner_prompt,
)

# run mission
planner.task = "Find tissues on the table, pick them up, find the trash bin and throw them away."
planner.go()
