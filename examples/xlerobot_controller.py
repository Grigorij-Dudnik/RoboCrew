from robocrew.core.tools import finish_task
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_left, create_turn_right
from robocrew.robots.XLeRobot.wheel_controls import XLeRobotWheels

prompt = "You are mobile household robot with two arms."

#set up wheel movement tools
wheel_arm_usb = "/dev/ttyACM1"    # provide your right arm usb port, as /dev/TTY0
wheel_controller = XLeRobotWheels(wheel_arm_usb)
move_forward = create_move_forward(wheel_controller)
turn_left = create_turn_left(wheel_controller)
turn_right = create_turn_right(wheel_controller)

# init agent
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    system_prompt=prompt,
    tools=[
        move_forward,
        turn_left,
        turn_right,
        finish_task,
    ],
    history_len=4,  # nr of last message-answer pairs to keep
    main_camera_usb_port="/dev/video0",  # provide usb port main camera connected to
    camera_fov=120,
    sounddevice_index=0,  # index of your microphone sounddevice
    debug_mode=False,
)

print("Agent initialized.")

# run agent with a sample task
agent.task = "Find kitchen in my house and go there."
agent.go()
