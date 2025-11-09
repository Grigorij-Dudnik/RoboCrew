import sys
import os
import cv2
from robocrew.core.tools import finish_task
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_left, create_turn_right, create_look_around
from robocrew.robots.XLeRobot.robot_controls import XLeRobotControler

prompt = "You are mobile household robot with two arms."


main_camera_usb_port="/dev/camera_center",

main_camera = cv2.VideoCapture(main_camera_usb_port)
main_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)


#set up wheel movement tools
wheel_arm_usb = "/dev/arm_right"    # provide your right arm usb port, as /dev/TTY0
head_arm_usb = "/dev/arm_left"
wheel_controler = XLeRobotControler(wheel_arm_usb)
head_controler = XLeRobotControler(head_arm_usb)
move_forward = create_move_forward(wheel_controler)
turn_left = create_turn_left(wheel_controler)
turn_right = create_turn_right(wheel_controler)
look_around = create_look_around(head_controler, main_camera)

# init agent
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    system_prompt=prompt,
    tools=[
        move_forward,
        turn_left,
        turn_right,
        look_around,
        finish_task,
    ],
    history_len=4,  # nr of last message-answer pairs to keep
    main_camera=main_camera,
    camera_fov=120,
    sounddevice_index=0,   # index of your microphone sounddevice
)

print("Agent initialized.")

# run agent
agent.go()
