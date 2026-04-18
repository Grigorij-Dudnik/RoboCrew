"""
The simplest example of agent that can drive XLeRobot.
"""

from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_right, create_turn_left
from robocrew.robots.XLeRobot.servo_controls import ServoControler

# set up main camera
main_camera = RobotCamera("/dev/camera_center") # camera usb port Eg: /dev/video0

#set up servo controler
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
servo_controler = ServoControler(right_arm_wheel_usb=right_arm_wheel_usb)

#set up tools
move_forward = create_move_forward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)

# init agent
agent = XLeRobotAgent(
    api_base = "http://100.69.195.44:8000/v1"
    model = "openai/nvidia/Cosmos-1.0-Prompt-Upsampler-12B-Text2World"
    api_key = "cos"
    tools=[
        move_forward,
        turn_left,
        turn_right,
    ],
    main_camera=main_camera,
    servo_controler=servo_controler,
)

agent.task = "Approach a human."

agent.go()
