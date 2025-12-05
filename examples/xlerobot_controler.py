import cv2
from robocrew.core.tools import finish_task
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_left, create_turn_right, create_look_around, create_vla_single_arm_manipulation
from robocrew.robots.XLeRobot.servo_controls import ServoControler


prompt = "You are mobile household robot with two arms. " \
"Use manipulation tools ONLY when you are right next to the " \
"target object (notebook), because your arms have short reach." \
" If you are not close enough to the target object, " \
" first move closer to it. If you drive into a wall, " \
"try going backwards and turning."

# set up main camera for head tools
main_camera_usb_port = "/dev/video0" # camera usb port Eg: /dev/video0
main_camera = cv2.VideoCapture(main_camera_usb_port)
main_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)


#set up wheel movement tools
wheel_arm_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
head_arm_usb = "/dev/arm_left"      # provide your left arm usb port. Eg: /dev/ttyACM0
wheel_controller = ServoControler(wheel_arm_usb, head_arm_usb)

move_forward = create_move_forward(wheel_controller)
turn_left = create_turn_left(wheel_controller)
turn_right = create_turn_right(wheel_controller)
look_around = create_look_around(wheel_controller, main_camera)
pick_up_notebook = create_vla_single_arm_manipulation(
    tool_name="Grab_a_notebook",
    tool_description="Grab a notebook from the table and put it to your basket. Use the tool only when you are very very close to table with a notebook, and look straingt on it.",
    task_prompt="Grab a notebook.",
    server_address="100.86.155.83:8080",
    policy_name="Grigorij/act_right_arm_grab_notebook",
    policy_type="act",
    arm_port=wheel_arm_usb,
    servo_controller=wheel_controller,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    main_camera_usb_port=main_camera_usb_port,
    policy_device="cpu"
)
give_notebook = create_vla_single_arm_manipulation(
    tool_name="Give_a_notebook_to_a_human",
    tool_description="Take a notebook from your basket and give it to human. Use the tool only when you are close to the human, and look straingt on him.",
    task_prompt="Grab a notebook and give it to a human.",
    server_address="localhost:8080",
    policy_name="Grigorij/act_right_arm_give_notebook",
    policy_type="act",
    arm_port=wheel_arm_usb,
    servo_controller=wheel_controller,
    camera_config={"main": {"index_or_path": "/dev/video0"}, "right_arm": {"index_or_path": "/dev/video2"}},
    main_camera_object=main_camera,
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
        # look_around,
        pick_up_notebook,
        give_notebook,
        #finish_task,
    ],
    history_len=6,  # nr of last message-answer pairs to keep
    main_camera_usb_port=main_camera,  # provide main camera.
    camera_fov=120,
    sounddevice_index=2,  # index of your microphone sounddevice
    debug_mode=False,
)

print("Agent initialized.")

wheel_controller.reset_head_position()

# run agent with a sample task
agent.task = "Grab a notebook from the table, go to human and give it to him."
agent.go()

# clean up
wheel_controller.disconnect()
main_camera.release()
