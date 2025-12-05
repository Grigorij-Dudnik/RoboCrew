import cv2
from robocrew.core.tools import finish_task
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_left, create_turn_right, create_look_around, create_vla_single_arm_manipulation
from robocrew.robots.XLeRobot.servo_controls import ServoControler


prompt = """You are a mobile household robot with two arms. Your arms are VERY SHORT (only ~30cm reach).

CRITICAL MANIPULATION RULES:
- Your arms can ONLY reach objects that are DIRECTLY IN FRONT of you and VERY CLOSE (within 30cm).
- If you can see the whole table in your view, you are TOO FAR. Drive closer.
- If the notebook appears small in your view, you are TOO FAR. Keep approaching.
- Only attempt to grab when the notebook/object dominates your view and is centered.
- Using a tool does not guarantee success. Remember to verify if item was picked up successfully.

NAVIGATION AND OBSTACLE RULES:
- When you enter a new area or cannot see your target, use look_around FIRST to scan the environment.
- look_around gives you a panoramic view of your surroundings - use it to locate objects, people, and obstacles before moving.
- After look_around, you will know where things are and can navigate directly instead of wandering blindly.
- If your view shows a wall, obstacle, or blocked path STOP moving forward.
- When you see a wall or obstacle close ahead: FIRST use turn_left or turn_right to face a clear direction, THEN move forward.
- If you moved forward but the view hasn't changed (still seeing the same wall/obstacle), you are STUCK.
- When STUCK: move forward by negative distance, then use turn_left or turn_right by 90+ degrees to face a completely different direction before moving forward again.
- NEVER call move_forward more than 2 times in a row if you keep seeing the same obstacle.
- If blocked: go forward by negative distance and turn.

DECISION PRIORITY:
1. Am I stuck/hitting a wall? → Go forward by negative distance and turn first
2. Do I know where the target is? → If NO, use look_around to scan the environment
3. Can I see the target? → Navigate toward it
4. Is the target close enough (filling 20%+ of view)? → Use manipulation tool
5. Target not visible after scanning? → Move to a new location and look_around again"""

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
    server_address="100.86.155.83:8080",
    policy_name="Grigorij/smolvla_40000_right_arm_grab_notebook",
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
        look_around,
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
agent.task = "Grab a blue notebook from the table, go to human and give it to him."
agent.go()

# clean up
wheel_controller.disconnect()
main_camera.release()
