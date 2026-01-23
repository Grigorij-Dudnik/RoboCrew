"""
 - The normal mode allows faster movement, while camera is looking higher.
 - The precision mode allows slower movement, while camera is looking lower for better movement precision and ability to see its own body.
 - Looking around tool uses the main camera to look left and right to find objects of interest.
 - Strafe movement is for going sideways without turning robot body.
"""

from robocrew.core.camera import RobotCamera
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent
from robocrew.robots.XLeRobot.tools import \
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

system_prompt = """
## ROBOT SPECS
- Mobile household robot with two arms
- Navigation modes: NORMAL (long-distance, forward camera) and PRECISION (close-range, downward camera)

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
- Enter when: target is at very bottom of view (intersects with view bottom edge), or stuck
- You will see: your arms, black basket (your body), and green reach lines
- Small movements only: 0.1-0.3m
- If target above green line: move forward 0.1m increments until base crosses below line
- Strafe more effective than turn for small adjustments (your body is wide). Combine both starfing and turning to have best results.
- Exit when: far from obstacles/target, or lost target - switch to NORMAL and look_around

## OPERATION SEQUENCE
1. Don't know where target is? → look_around
2. Target visible but far? → NORMAL mode, turn to center it, move_forward
3. Target at bottom of view? → Switch to PRECISION mode
4. In PRECISION, target off-center? → Strafe to center it
5. In PRECISION, target above green line? → Move forward until below line
6. Stuck or lost target? → PRECISION mode + move_backward/strafe OR switch to NORMAL + look_around
"""

# set up main camera
main_camera = RobotCamera("/dev/camera_center") # camera usb port Eg: /dev/video0

#set up wheel movement tools
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
left_arm_head_usb = "/dev/arm_left"      # provide your left arm usb port. Eg: /dev/ttyACM0
servo_controler = ServoControler(right_arm_wheel_usb, left_arm_head_usb)

#set up tools
move_forward = create_move_forward(servo_controler)
move_backward = create_move_backward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)
strafe_left = create_strafe_left(servo_controler)
strafe_right = create_strafe_right(servo_controler)

look_around = create_look_around(servo_controler, main_camera)
go_to_precision_mode = create_go_to_precision_mode(servo_controler)
go_to_normal_mode = create_go_to_normal_mode(servo_controler)

# init agent
agent = XLeRobotAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[
        move_forward,
        move_backward,
        strafe_left,
        strafe_right,
        turn_left,
        turn_right,
        look_around,
        go_to_precision_mode,
        go_to_normal_mode,
    ],
    history_len=8,              # nr of last message-answer pairs to keep
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
)

agent.task = "Find human and follow him closely."

agent.go()