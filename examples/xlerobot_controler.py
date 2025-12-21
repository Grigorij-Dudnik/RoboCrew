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
import torch

_original_restore = torch.serialization.default_restore_location

def force_cpu_restore(storage, location):
    # Regardless of what device the server said (e.g., 'cuda:0'), 
    # we force it to load on 'cpu'
    return _original_restore(storage, "cpu")

torch.serialization.default_restore_location = force_cpu_restore
# --- FIX END ---




system_prompt = """
## ROBOT SPECS
- Mobile household robot with two arms
- ARM REACH: ~30cm only (VERY SHORT)
- Navigation modes: NORMAL (long-distance, forward camera) and PRECISION (close-range, downward camera)

## MANIPULATION RULES - CRITICAL
- ALWAYS switch to PRECISION mode BEFORE any manipulation attempt
- GREEN LINES show your arm reach boundary (only visible in PRECISION mode)
- ONLY manipulate when the BASE of target object is BELOW the green line
- If target is above green line: TOO FAR - move closer first using small forward steps (0.1m)
- Target must be CENTERED in view (middle of image) before grabbing
- If off-center: strafe or turn to align first
- Always verify success after using a tool - retry if failed

## NAVIGATION RULES
- Can't see target? Use look_around FIRST (don't wander blindly)
- Check angle grid at top of image - target must be within ±15° of center before moving forward
- Watch for obstacles in your path - if obstacle blocks the way, navigate around it first
- STUCK (standing on same place after moving)? Switch to PRECISION, use move_backward or strafe
- Never call move_forward 3+ times if nothing changes

## NORMAL MODE (Long-distance)
- Use for: navigation 0.5-3m, exploring
- If target is off-center: use turn_left or turn_right to align BEFORE moving forward
- Before EVERY move_forward: verify target is centered (±15° on angle grid)
- Reference floor meters only if floor visible and scale not on objects
- Watch for obstacles between you and target - plan path to avoid them
- Switch to PRECISION ONLY when target is at the VERY BOTTOM of camera view (almost touching bottom edge)

## PRECISION MODE (Close-range)
- Enter when: target is at very bottom of view (intersectgs with view bottom edge), stuck, or about to manipulate
- You will see: your arms, black basket (your body), and green reach lines
- Small movements only: 0.1-0.3m
- Green lines show arm reach - check if BASE of target is below green line before manipulating
- If target above green line: move forward 0.1m increments until base crosses below line
- Strafe more effective than turn for small adjustments (your body is wide). Combine both starfing and turning to have best results.
- Exit when: far from obstacles/target, or lost target - switch to NORMAL and look_around

## OPERATION SEQUENCE
1. Don't know where target is? → look_around
2. Target visible but far? → NORMAL mode, turn to center it, move_forward
3. Target at bottom of view? → Switch to PRECISION mode
4. In PRECISION, target off-center? → Strafe to center it
5. In PRECISION, target above green line? → Move forward until below line
6. Target centered AND below green line? → Use manipulation tool
7. Stuck or lost target? → PRECISION mode + move_backward/strafe OR switch to NORMAL + look_around
"""


# set up main camera
main_camera = RobotCamera("/dev/video0") # camera usb port Eg: /dev/video0

#set up wheel movement tools
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
left_arm_head_usb = "/dev/arm_left"      # provide your left arm usb port. Eg: /dev/ttyACM0
servo_controler = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

move_forward = create_move_forward(servo_controler)
move_backward = create_move_backward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)
strafe_left = create_strafe_left(servo_controler)
strafe_right = create_strafe_right(servo_controler)

look_around = create_look_around(servo_controler, main_camera)
go_to_precision_mode = create_go_to_precision_mode(servo_controler)
go_to_normal_mode = create_go_to_normal_mode(servo_controler)

pick_up_notebook = create_vla_single_arm_manipulation(
    tool_name="Grab_a_notebook",
    tool_description="Manipulation tool to grab a notebook from the table and put it to your basket. Use the tool only when you are very very close to table with a notebook, and look straingt on it.",
    task_prompt="Grab a notebook.",
    server_address="100.86.155.83:8080",
    policy_name="Grigorij/pi05_right-arm-grab-notebook",
    policy_type="pi05",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/video4"}},
    # camera_config={"camera1": {"index_or_path": "/dev/camera_center"}, "camera2": {"index_or_path": "/dev/video4"}},   # for smolvla
    main_camera_object=main_camera,
    policy_device="cuda",
    execution_time=90,
    fps=15,
    actions_per_chunk=30,
)
give_notebook = create_vla_single_arm_manipulation(
    tool_name="Give_a_notebook_to_a_human",
    tool_description="Manipulation tool to take a notebook from your basket and give it to human. Use the tool only when you are close to the human (base of human is below green line), and look straingt on him.",
    task_prompt="Grab a notebook and give it to a human.",
    server_address="100.86.155.83:8080",
    policy_name="Grigorij/act_right_arm_give_notebook",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cuda",
    execution_time=45,
    fps=15,
    actions_per_chunk=30,
)
# init agent
agent = LLMAgent(
    model="google_genai:gemini-3-flash-preview",
    #model="google_genai:gemini-robotics-er-1.5-preview",
    system_prompt=system_prompt,
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
    servo_controler=servo_controler,
    debug_mode=True,
)

print("Agent initialized.")

# run agent with a sample task
agent.task = "Approach blue notebook, grab it from the table and give it to human. Do not approach human until you grabbed a notebook."
#agent.task = "Strafe right all the time."

agent.go()