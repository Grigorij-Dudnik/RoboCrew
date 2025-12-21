"""
The simplest example of agent that can drive XLeRobot.
"""

from robocrew.core.camera import RobotCamera
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import \
    create_move_backward, \
    create_move_forward, \
    create_look_around, \
    create_turn_right, \
    create_turn_left
from robocrew.robots.XLeRobot.servo_controls import ServoControler

# set up main camera
main_camera = RobotCamera("/dev/video0") # camera usb port Eg: /dev/video0

#set up servo controler
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
left_arm_head_usb = "/dev/arm_left"      # provide your left arm usb port. Eg: /dev/ttyACM0
servo_controler = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

#set up tools
move_forward = create_move_forward(servo_controler)
move_backward = create_move_backward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)
look_around = create_look_around(servo_controler, main_camera)

# init agent
agent = LLMAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[
        move_forward,
        move_backward,
        turn_left,
        turn_right,
        look_around,
    ],
    main_camera=main_camera,  # provide main camera.
    servo_controler=servo_controler,
)

agent.task = "Approach a human."

agent.go()