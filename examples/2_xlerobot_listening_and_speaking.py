"""
The simplest example of agent that can listen and speak, aside from driving XLeRobot.
"""

from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_right, create_turn_left
from robocrew.robots.XLeRobot.servo_controls import ServoControler

# set up main camera
main_camera = RobotCamera("/dev/camera_center") # camera usb port Eg: /dev/video0

# set up servo controler
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
servo_controler = ServoControler(right_arm_wheel_usb=right_arm_wheel_usb)

# set up tools
move_forward = create_move_forward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)

# init agent
agent = XLeRobotAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[
        move_forward,
        turn_left,
        turn_right,
    ],

    main_camera=main_camera,
    servo_controler=servo_controler,
    sounddevice_index_or_alias="mic_main",    # provide your microphone device index.
    wakeword="Bob",         # set custom wakeword (default is "robot").
    tts=True,               # uncomment for text-to-speech, to make robot speak (work in progress).
)

agent.task = "Wait for the task"

agent.go()
