"""
This example demonstrates MolmoAct2 arm manipulation on the XLeRobot SO-101 arm.

The MolmoAct2 model runs out-of-process on a GPU box. Start the server there first:

    python -m robocrew.robots.XLeRobot.molmoact.serve

Then run this example on the robot box. The create_molmoact2_single_arm_manipulation
tool captures the scene + wrist cameras, reads the arm state, streams them to the
server over TCP, and drives the arm with the predicted action chunks (temporal
ensembling) for `execution_time` seconds.
"""

from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.robots.XLeRobot.tools import \
    create_molmoact2_single_arm_manipulation, \
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
main_camera = RobotCamera("/dev/camera_center")  # camera usb port Eg: /dev/video0

# set up servo controler
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
left_arm_head_usb = "/dev/arm_left"       # provide your left arm usb port. Eg: /dev/ttyACM0
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


# Remember to start the MolmoAct2 server on the GPU box first:
#   python -m robocrew.robots.XLeRobot.molmoact.serve

manipulate_arm = create_molmoact2_single_arm_manipulation(
    tool_name="Manipulate_with_arm",
    tool_description=(
        "Perform a table-top manipulation with the right arm using the MolmoAct2 "
        "model. Pass an `instruction`: a short, concrete command for what to do this "
        "run, e.g. 'pick up the lemon and drop it in the red bowl' or 'push the cube "
        "to the left'. Use only when very close to the table and looking straight at it."
    ),
    server_address="greg-pc:5005",   # host:port of the MolmoAct2 server (GPU box)
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={
        "main": {"index_or_path": "/dev/camera_center"},
        "wrist": {"index_or_path": "/dev/camera_right"},
    },
    main_camera_object=main_camera,
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
        manipulate_arm,
        go_to_precision_mode,
        go_to_normal_mode,
    ],
    history_len=8,
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
)

agent.task = "Approach the table, then pick up the lemon and drop it in the red bowl."


agent.go()
