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


pick_up_tissue = create_vla_single_arm_manipulation(
    tool_name="Grab_a_tissue",
    tool_description="Manipulation tool to grab a tissue from the table and put it to your basket. Use the tool only when you are very very close to table with a tissue (tissue should be under green line), and look straight on it. Edge of the table should touch your front edge.",
    task_prompt="Collect trash to the bin.",
    server_address="greg-pc:8080",
    policy_name="Grigorij/smolvla_collect_leaflet",
    policy_type="smolvla",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"camera1": {"index_or_path": "/dev/camera_center"}, "camera2": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cpu",
    execution_time=120,
)

put_trash_bag_to_bin = create_vla_single_arm_manipulation(
    tool_name="Throw_out_trash_bag_to_the_bin",
    tool_description="Manipulation tool to take a trash bag with a trash you collected and throw it into the bin. Use the tool only when you are close to the bin, and look straight on it.",
    task_prompt="Throw out the trash bag to the bin.",
    server_address="greg-pc:8080",
    policy_name="Grigorij/smolvla_trow_out_thrash_reactivation",
    policy_type="smolvla",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"camera1": {"index_or_path": "/dev/camera_center"}, "camera2": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cpu",
    execution_time=120,
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
        pick_up_tissue,
        put_trash_bag_to_bin,
        go_to_precision_mode,
        go_to_normal_mode,
        save_checkpoint,
    ],
    history_len=8,
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
)

agent.task = """
Collect all tissues from the table. After table is clear, go to thrash bins and throw out trash to the BLACK bin.
Come very close to the table before grabbing a tissues! There should be no space between you and table, tissue should bi udner green mark, and you should look straight on it. After you collect tissue, put it to your basket. When you have at least 3 tissues in your basket, go to the bin and throw out the trash bag with tissues into the BLACK bin. Be careful, if you throw out trash bag into wrong bin (GREY or BLUE), you will fail the task.
"""

agent.go()
