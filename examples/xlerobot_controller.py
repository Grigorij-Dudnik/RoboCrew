from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.tools import finish_task
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_left, create_turn_right
from robocrew.robots.XLeRobot.wheel_controls import XLeRobotWheels

# Set up wheels
wheel_controller = XLeRobotWheels("/dev/ttyACM1")

# Create movement tools
move_forward = create_move_forward(wheel_controller)
turn_left = create_turn_left(wheel_controller)
turn_right = create_turn_right(wheel_controller)
# Create agent
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    tools=[move_forward, turn_left, turn_right, finish_task],
    main_camera_usb_port="/dev/video0",  # provide usb port main camera connected to
    camera_fov=110,
    # sounddevice_index=0,  # Your mic device
    # wakeword="robot",  # The robot listens for this word in your speech
    history_len=4,
    debug_mode=False,
)
agent.task = "Find kitchen in my house and go there."
agent.go() 