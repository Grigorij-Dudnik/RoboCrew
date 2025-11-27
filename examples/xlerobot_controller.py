import cv2
from robocrew.core.tools import finish_task
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_left, create_turn_right, create_look_around, create_vla_arm_manipulation
from robocrew.robots.XLeRobot.wheel_controls import XLeRobotWheels


prompt = "You are mobile household robot with two arms."

# set up main camera for head tools
main_camera_usb_port = "/dev/video0" # camera usb port Eg: /dev/video0
main_camera = cv2.VideoCapture(main_camera_usb_port)
main_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)


#set up wheel movement tools
wheel_arm_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
head_arm_usb = "/dev/arm_left"      # provide your left arm usb port. Eg: /dev/ttyACM0
wheel_controller = XLeRobotWheels(wheel_arm_usb)

move_forward = create_move_forward(wheel_controller)
turn_left = create_turn_left(wheel_controller)
turn_right = create_turn_right(wheel_controller)
look_around = create_look_around(wheel_controller, main_camera)
pick_up_cup = create_vla_arm_manipulation(
    "localhost:8080",
    "Grigorij/act_xle_cup_to_box",
    "act",
    wheel_arm_usb,
    camera_config={"main": {"index_or_path": "/dev/video0"}, "left_arm": {"index_or_path": "/dev/video2"}},
    main_camera_object = main_camera,
    main_camera_usb_port=main_camera_usb_port,
    policy_device="cpu"
)

# init agent
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    system_prompt=prompt,
    tools=[
        move_forward,
        turn_left,
        turn_right,
        look_around,
        pick_up_cup,
        finish_task,
    ],
    history_len=4,  # nr of last message-answer pairs to keep
    main_camera_usb_port=main_camera,  # provide main camera.
    camera_fov=120,
    sounddevice_index=2,  # index of your microphone sounddevice
    debug_mode=False,
)

print("Agent initialized.")

# run agent with a sample task
agent.task = "Grab the cup, and then turn right"
agent.go()

# clean up
wheel_controller.disconnect()
main_camera.release()
