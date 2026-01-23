"""
This example demonstrates how to activate arm manipulation of your XLeRobot.
vla_single_arm_manipulation tools allow XLeRobot to use its arm for manipulating objects with pretrained VLA policies.
"""

from robocrew.core.camera import RobotCamera
from robocrew.core.tools import save_checkpoint
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
from pathlib import Path


prompt_path = Path(__file__).parent.parent.resolve() / "src/robocrew/robots/XLeRobot/xlerobot.prompt"
with open(prompt_path, "r") as f:
    system_prompt = f.read()

# set up main camera
main_camera = RobotCamera("/dev/camera_center") # camera usb port Eg: /dev/video0

#set up servo controler
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
left_arm_head_usb = "/dev/arm_left"      # provide your left arm usb port. Eg: /dev/ttyACM0
servo_controler = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

#set up tools
move_forward = create_move_forward(servo_controler)
move_backward = create_move_backward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)
strafe_left = create_strafe_left(servo_controler)
strafe_right = create_strafe_right(servo_controler)

look_around = create_look_around(servo_controler, main_camera)
go_to_precision_mode = create_go_to_precision_mode(servo_controler)
go_to_normal_mode = create_go_to_normal_mode(servo_controler)


#   Remember to run the VLA server before using manipulation tools:
#   python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080


pick_up_notebook = create_vla_single_arm_manipulation(
    tool_name="Grab_a_notebook",
    tool_description="Manipulation tool to grab a notebook from the table and put it to your basket. Use the tool only when you are very very close to table with a notebook, and look straingt on it.",
    task_prompt="Grab a notebook.",
    server_address="0.0.0.0:8080",
    policy_name="Grigorij/act_right-arm-grab-notebook-2",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cpu",
)

give_notebook = create_vla_single_arm_manipulation(
    tool_name="Give_a_notebook_to_a_human",
    tool_description="Manipulation tool to take a notebook from your basket and give it to human. Use the tool only when you are close to the human (base of human is below green line), and look straingt on him.",
    task_prompt="Grab a notebook and give it to a human.",
    server_address="0.0.0.0:8080",
    policy_name="Grigorij/act_right_arm_give_notebook",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cpu",
    execution_time=45,
)

# init agent
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
        pick_up_notebook,
        give_notebook,
        go_to_precision_mode,
        go_to_normal_mode,
        save_checkpoint,
    ],
    history_len=8,
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
)

agent.task = "Approach blue notebook, grab it from the table and give it to human. Do not approach human until you grabbed a notebook."

agent.go()