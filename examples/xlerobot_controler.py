from robocrew.core.camera import RobotCamera
from robocrew.core.tools import finish_task, save_checkpoint
from robocrew.core.LLMAgent import LLMAgent
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



# --- FIX START: Force all incoming tensors to CPU ---
# This prevents the "RuntimeError: Attempting to deserialize object on a CUDA device"
# by intercepting the load call and redirecting it to 'cpu'.
import torch

_original_restore = torch.serialization.default_restore_location

def force_cpu_restore(storage, location):
    # Regardless of what device the server said (e.g., 'cuda:0'), 
    # we force it to load on 'cpu'
    return _original_restore(storage, "cpu")

torch.serialization.default_restore_location = force_cpu_restore
# --- FIX END ---


# set up main camera
main_camera = RobotCamera("/dev/video0") # camera usb port Eg: /dev/video0

#set up wheel movement tools
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
left_arm_head_usb = "/dev/arm_left"      # provide your left arm usb port. Eg: /dev/ttyACM0
servo_controller = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

move_forward = create_move_forward(servo_controller)
move_backward = create_move_backward(servo_controller)

turn_left = create_turn_left(servo_controller)
turn_right = create_turn_right(servo_controller)

strafe_left = create_strafe_left(servo_controller)
strafe_right = create_strafe_right(servo_controller)

look_around = create_look_around(servo_controller, main_camera)
go_to_precision_mode = create_go_to_precision_mode(servo_controller)
go_to_normal_mode = create_go_to_normal_mode(servo_controller)

pick_up_notebook = create_vla_single_arm_manipulation(
    tool_name="Grab_a_notebook",
    tool_description="Grab a notebook from the table and put it to your basket. Use the tool only when you are very very close to table with a notebook, and look straingt on it.",
    task_prompt="Grab a notebook.",
    server_address="100.86.155.83:8080",
    policy_name="Grigorij/act_right_arm_grab_notebook",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controller=servo_controller,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cuda",
    execution_time=45,
    fps=15,
    actions_per_chunk=30,
)
give_notebook = create_vla_single_arm_manipulation(
    tool_name="Give_a_notebook_to_a_human",
    tool_description="Take a notebook from your basket and give it to human. Use the tool only when you are close to the human (base of human is below green line), and look straingt on him.",
    task_prompt="Grab a notebook and give it to a human.",
    server_address="100.86.155.83:8080",
    policy_name="Grigorij/act_right_arm_give_notebook",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controller=servo_controller,
    camera_config={"main": {"index_or_path": "/dev/video0"}, "right_arm": {"index_or_path": "/dev/video2"}},
    main_camera_object=main_camera,
    policy_device="cuda",
    execution_time=45,
    fps=15,
    actions_per_chunk=30,
)
# init agent
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    tools=[
        move_forward,
        move_backward,
        strafe_left,
        strafe_right,
        turn_left,
        turn_right,
        look_around,
        pick_up_notebook,
        give_notebook,
        go_to_precision_mode,
        go_to_normal_mode,
        save_checkpoint,
        #finish_task,
    ],
    history_len=8,  # nr of last message-answer pairs to keep
    main_camera=main_camera,  # provide main camera.
    camera_fov=90,
    sounddevice_index=2,  # index of your microphone sounddevice
    debug_mode=True,
)

print("Agent initialized.")

servo_controller.reset_head_position()

# run agent with a sample task
agent.task = "Grab blue notebook from the table and give it to human."
#agent.task = "Strafe right all the time."
try:
    agent.go()
except KeyboardInterrupt:
    print("Interrupted by user, shutting down...")
finally:
    # clean up
    servo_controller.disconnect()
    main_camera.release()