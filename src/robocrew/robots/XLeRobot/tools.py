import base64

from pathlib import Path

import math
import cv2
import numpy as np
from langchain_core.tools import tool  # type: ignore[import]
from lerobot.async_inference.robot_client import RobotClient
from lerobot.async_inference.configs import RobotClientConfig
from lerobot.robots.so_follower.config_so_follower import SOFollowerConfig
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from lerobot.motors import Motor, MotorNormMode
from lerobot.motors.feetech import FeetechMotorsBus
from robocrew.robots.XLeRobot.groot_client import PolicyClient

from robocrew.core.utils import stop_listening_during_tool_execution
from robocrew.robots.XLeRobot.servo_controls import DEFAULT_ARM_CALIBRATION_DIR
import time
import threading


def create_move_forward(servo_controller, sound_receiver=None):
    @tool
    @stop_listening_during_tool_execution(sound_receiver)
    def move_forward(distance_meters: float) -> str:
        """Drives the robot forward (or backward) for a specific distance."""

        distance = float(distance_meters)
        if distance >= 0:
            servo_controller.go_forward(distance)
        else:
            servo_controller.go_backward(-distance)
        return f"Moved {'forward' if distance >= 0 else 'backward'} {abs(distance):.2f} meters."

    return move_forward

def create_move_backward(servo_controller, sound_receiver=None):
    @tool
    @stop_listening_during_tool_execution(sound_receiver)
    def move_backward(distance_meters: float) -> str:
        """Drives the robot forward (or backward) for a specific distance."""

        distance = float(distance_meters)
        servo_controller.go_backward(distance)
        return f"Moved backward {distance} meters."

    return move_backward

def create_turn_right(servo_controller, sound_receiver=None):
    @tool
    @stop_listening_during_tool_execution(sound_receiver)
    def turn_right(angle_degrees: float) -> str:
        """Turns the robot right by angle in degrees. Use only when robot body not touches any obstacle."""
        angle = float(angle_degrees)
        servo_controller.turn_right(angle)
        time.sleep(0.4)  # wait a bit after turn for stabilization
        return f"Turned right by {angle} degrees."

    return turn_right

def create_turn_left(servo_controller, sound_receiver=None):
    @tool
    @stop_listening_during_tool_execution(sound_receiver)
    def turn_left(angle_degrees: float) -> str:
        """Turns the robot left by angle in degrees. Use only when robot body not touches any obstacle."""
        angle = float(angle_degrees)
        servo_controller.turn_left(angle)
        time.sleep(0.4)  # wait a bit after turn for stabilization
        return f"Turned left by {angle} degrees."

    return turn_left


def create_strafe_left(servo_controller, sound_receiver=None):
    @tool
    @stop_listening_during_tool_execution(sound_receiver)
    def strafe_left(distance_meters: float) -> str:
        """Moves the robot sideways left by a specific distance in meters."""
        distance = float(distance_meters)
        servo_controller.strafe_left(distance)
        return f"Strafed left by {distance} meters."

    return strafe_left

def create_strafe_right(servo_controller, sound_receiver=None):
    @tool
    @stop_listening_during_tool_execution(sound_receiver)
    def strafe_right(distance_meters: float) -> str:
        """Moves the robot sideways right by a specific distance in meters."""
        distance = float(distance_meters)
        servo_controller.strafe_right(distance)
        return f"Strafed right by {distance} meters."

    return strafe_right

def create_go_to_precision_mode(servo_controller):
    @tool
    def go_to_precision_mode() -> str:
        """Sets the robot to precision movement mode. Use it when close to obstacles or target."""
        servo_controller.turn_head_to_vla_position(50)
        return "Robot set to precision movement mode."

    return go_to_precision_mode

def create_go_to_normal_mode(servo_controller):
    @tool
    def go_to_normal_mode() -> str:
        """Sets the robot to normal movement mode for long distance rides."""
        servo_controller.reset_head_position()
        return "Robot set to normal movement mode."

    return go_to_normal_mode


def create_look_around(servo_controller, main_camera):
    @tool
    def look_around() -> list:
        """Look around yourself to find a thing you looking for or to understand an envinronment."""
        movement_delay = 0.9  # seconds
        print("Looking around...")
        servo_controller.turn_head_yaw(-120)
        time.sleep(movement_delay)
        image_1 = main_camera.capture_image(center_angle=-120)
        image_1_64 = base64.b64encode(image_1).decode('utf-8')
        servo_controller.turn_head_yaw(-40)
        time.sleep(movement_delay)
        image_2 = main_camera.capture_image(center_angle=-40)
        image_2_64 = base64.b64encode(image_2).decode('utf-8')  
        servo_controller.turn_head_yaw(40)
        time.sleep(movement_delay)
        image_3 = main_camera.capture_image(center_angle=40)
        image_3_64 = base64.b64encode(image_3).decode('utf-8')
        servo_controller.turn_head_yaw(120)
        time.sleep(movement_delay)
        image_4 = main_camera.capture_image(center_angle=120)
        image_4_64 = base64.b64encode(image_4).decode('utf-8')
        servo_controller.turn_head_yaw(0)  # look forward again
        time.sleep(movement_delay)

        return "Looked around", [
            {"type": "text", "text": "Left"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_1_64}",}},
            {"type": "text", "text": "Left-Center"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_2_64}"}},
            {"type": "text", "text": "Right-Center"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_3_64}"}},
            {"type": "text", "text": "Right"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_4_64}"}},         
        ]
    return look_around


def create_vla_single_arm_manipulation(
        tool_name: str,
        tool_description: str,
        task_prompt: str,
        server_address: str,
        policy_name: str, 
        policy_type: str, 
        arm_port: str,
        servo_controler, 
        camera_config: dict[str, dict], 
        main_camera_object,
        execution_time: int = 30,
        policy_device: str = "cuda",
        fps: int = 30,
        actions_per_chunk: int = 50,
        load_on_startup: bool = True,
    ):
    """Creates a tool that makes the robot pick up a cup using its arm.
    Args:
        tool_name (str): The name of the tool AI agent will see.
        tool_description (str): The description of the tool AI agent will see.
        task_prompt (str): The task prompt to give to the VLA policy.
        server_address (str): The address of the server to connect to.
        policy_name (str): The name or path of the pretrained policy.
        policy_type (str): The type of policy to use.
        arm_port (str): The USB port of the robot's arm.
        camera_config (dict, optional): Lerobot-type camera configuration. (E.g., "{ main: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30}, left_arm: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30}}")
        execution_time (int, optional): Time in seconds to run the manipulation.
        policy_device (str, optional): The device to run the policy on. Defaults to "cuda".
        fps (int, optional): The fps to run the policy at.
        actions_per_chunk (int, optional): Number of actions VLA calculates at once.
        load_on_startup (bool, optional): Whether to load the VLA policy on startup. If False, the policy will be loaded every time the tool used, which may cause a delay. If True for many tools, you may overload server's GPU.
    """

    right_port = getattr(servo_controler, "right_arm_wheel_usb", None)
    left_port = getattr(servo_controler, "left_arm_head_usb", None)
    arm_side = (
        "right" if arm_port == right_port else
        "left" if arm_port == left_port else
        "right" if "right" in str(arm_port).lower() else
        "left" if "left" in str(arm_port).lower() else
        None
    )


    configured_cameras = {}
    for cam_name, cam_settings in camera_config.items():
        # Unpack the dictionary settings directly into the Config class
        configured_cameras[cam_name] = OpenCVCameraConfig(
            index_or_path=cam_settings["index_or_path"],
            width=cam_settings.get("width", 640),
            height=cam_settings.get("height", 480),
            fps=cam_settings.get("fps", 30)
        )

    robot_config = SOFollowerConfig(
        port=arm_port,
        cameras=configured_cameras,
    )

    robot_config.type = "so101_follower"

    robot_config.id="robot_arm"

    # LeRobot expects a Path-like object here (it calls mkdir on this value).
    robot_config.calibration_dir = Path(DEFAULT_ARM_CALIBRATION_DIR).expanduser()
    

    cfg = RobotClientConfig(
        robot=robot_config,
        task=task_prompt,
        server_address=server_address,
        policy_type=policy_type,
        pretrained_name_or_path=policy_name,
        policy_device=policy_device,
        actions_per_chunk=actions_per_chunk,
        chunk_size_threshold=0.5,
        fps=fps
    )


    preloaded_client = None

    if load_on_startup:
        print(f" Loading Policy for {tool_name}...")
        # release main camera from agent
        main_camera_object.release()
        time.sleep(1) 

        preloaded_client = RobotClient(cfg)
        preloaded_client.robot.disconnect()

        # Warm up once at startup so server loads policy weights before first real execution.
        warmup_client = RobotClient(cfg)
        warmup_client.robot.disconnect()

        #assign main camera back to agent
        time.sleep(0.5)
        main_camera_object.reopen()
    
    @tool
    def tool_name_to_override() -> str:
        """Tool description to override."""
        print("Manipulation tool activated")

        servo_controler.set_saved_position("cobra", arm_side=arm_side)

        servo_controler.turn_head_to_vla_position()
        # release main camera from agent, so arm policy can use it
        main_camera_object.release()
        time.sleep(1)  # give some time to release camera

        client = None
        try:

            if not load_on_startup:
                client = RobotClient(cfg)
            else:
                client = preloaded_client
                client.robot.connect()

            # Use a fresh RobotClient per invocation so worker threads can be stopped cleanly.
            client = RobotClient(cfg)

            if not client.start():
                return "Failed to connect to robot server."

            threading.Thread(target=client.receive_actions, daemon=True).start()
            threading.Timer(execution_time, _shutdown_robot_client, args=(client,)).start()
            try:
                client.control_loop(task=task_prompt)
            except Exception:
                pass
        
        finally:

            #if client and client.robot.is_connected:
            if not load_on_startup and client:
                client.stop()
            # Re-open main camera for agent use. 
            time.sleep(1)
            main_camera_object.reopen()
            # set head back to precize mode
            servo_controler.turn_head_to_vla_position(50)

            if client:
                try:
                    client.stop()
                except Exception:
                    pass
            # Re-open main camera for agent use. 
            time.sleep(1)
            main_camera_object.reopen()
            time.sleep(0.3)
            # set head back to precize mode
            servo_controler.turn_head_to_vla_position(50)
            servo_controler.set_saved_position("default", arm_side="both")  # optionally set a default position for both arms after manipulation

        
        return "Arm manipulation done"
    
    tool_name_to_override.name = tool_name
    tool_name_to_override.description = tool_description

    return tool_name_to_override


def _shutdown_robot_client(client: "RobotClient") -> None:
    """Gracefully stop the control loop before disconnecting the robot.

    Signals the running control loop to exit on its next iteration before
    hardware disconnection, preventing race conditions.
    """
    client.stop()


# ── MolmoAct2 ────────────────────────────────────────────────────────────────
# Fixed runtime knobs for the MolmoAct2 SO-101 policy (server owns dtype/num_steps).
# The standard LeRobot v3.0 → v2.1 SO-100/101 joint conversion:
_MOLMOACT_JOINT_OFFSETS = "0,90,90,0,0,0"
_MOLMOACT_JOINT_SIGNS = "1,-1,1,1,1,1"
_MOLMOACT_WRIST_FLIP = "180"
_MOLMOACT_FPS = 30.0
_MOLMOACT_ENSEMBLE_M = 0.5
_MOLMOACT_SMOOTH_ALPHA = 1.0
_MOLMOACT_MAX_STEP_DEG = 15.0
_MOLMOACT_SCENE_ONLY = False


def create_molmoact2_single_arm_manipulation(
        tool_name: str,
        tool_description: str,
        server_address: str,
        arm_port: str,
        servo_controler,
        camera_config: dict[str, dict],
        main_camera_object,
        execution_time: int = 30,
    ):
    """Creates a tool that runs MolmoAct2 on the SO-101 arm via a remote server.

    Unlike the single-policy VLA tool, MolmoAct2 is prompt-driven: the LLM passes
    a fresh natural-language `instruction` on every call, so one tool can perform
    any manipulation the model understands — no per-task policy needed.

    Mirrors create_vla_single_arm_manipulation's lifecycle, but the GPU model
    runs out-of-process in molmoact/serve.py and the arm is driven by the
    MolmoAct2 async producer/consumer (temporal ensembling). Start the server
    first on the GPU box: `python -m robocrew.robots.XLeRobot.molmoact.serve`.

    Args:
        tool_name (str): Name the AI agent sees.
        tool_description (str): Description the AI agent sees. Should tell the LLM
            what kinds of instructions the arm can carry out.
        server_address (str): "host:port" of the MolmoAct2 server, e.g. "greg-pc:5005".
        arm_port (str): USB port of the SO-101 follower arm.
        servo_controler: Robot servo controller (positions arm/head).
        camera_config (dict): {"main": {"index_or_path": ...}, "wrist": {"index_or_path": ...}}.
            "main" is the scene/side view; "wrist" is the in-hand camera.
        main_camera_object: Agent's main camera — released before and restored after.
        execution_time (int): Seconds to run the policy.
    """
    # Lazy imports so tools.py keeps importing even if molmoact deps (e.g. Pillow)
    # aren't installed on a given machine.
    from robocrew.robots.XLeRobot.molmoact.client import RemotePolicyClient
    from robocrew.robots.XLeRobot.molmoact.hardware import (
        FollowerArm, OpenCVCapture, WristCamera, warmup_cameras,
    )
    from robocrew.robots.XLeRobot.molmoact.runtime import AsyncPolicyRunner, RuntimeConfig
    from robocrew.robots.XLeRobot.molmoact.frame_transforms import (
        parse_joint_offsets, parse_joint_signs, parse_joint_limits,
    )

    right_port = getattr(servo_controler, "right_arm_wheel_usb", None)
    left_port = getattr(servo_controler, "left_arm_head_usb", None)
    arm_side = (
        "right" if arm_port == right_port else
        "left" if arm_port == left_port else
        "right" if "right" in str(arm_port).lower() else
        "left" if "left" in str(arm_port).lower() else
        None
    )

    host, _, port = server_address.partition(":")
    scene_cam = camera_config["main"]["index_or_path"]
    wrist_cam = camera_config["wrist"]["index_or_path"]

    signs = parse_joint_signs(_MOLMOACT_JOINT_SIGNS)
    offsets = parse_joint_offsets(_MOLMOACT_JOINT_OFFSETS)
    joint_min = parse_joint_limits(None, -np.inf)
    joint_max = parse_joint_limits(None, np.inf)

    @tool
    def tool_name_to_override(instruction: str) -> str:
        """Tool description to override.

        Args:
            instruction: A concrete natural-language command describing what the
                arm should do this run, e.g. "pick up the lemon".
        """
        print(f"MolmoAct2 manipulation tool activated: {tool_name} | instruction={instruction!r}")

        servo_controler.set_saved_position("cobra", arm_side=arm_side)
        servo_controler.turn_head_to_vla_position()
        main_camera_object.release()
        time.sleep(1)

        policy = scene = wrist = follower = None
        try:
            policy = RemotePolicyClient(host, int(port))
            scene = OpenCVCapture(scene_cam)
            wrist = WristCamera(wrist_cam, flip=_MOLMOACT_WRIST_FLIP)
            warmup_cameras(wrist, scene)

            follower = FollowerArm(port=arm_port)
            follower.set_target(follower.get_state())  # latch pose before torque-on

            config = RuntimeConfig(
                prompt=instruction,
                exec_hz=_MOLMOACT_FPS,
                max_step_deg=_MOLMOACT_MAX_STEP_DEG,
                smooth_alpha=_MOLMOACT_SMOOTH_ALPHA,
                ensemble_m=_MOLMOACT_ENSEMBLE_M,
                scene_only=_MOLMOACT_SCENE_ONLY,
            )

            with AsyncPolicyRunner(
                policy=policy, follower=follower, wrist=wrist, scene=scene,
                signs=signs, offsets=offsets,
                joint_min=joint_min, joint_max=joint_max,
                config=config,
            ):
                time.sleep(execution_time)

        finally:
            for fn in (
                lambda: follower.disconnect() if follower else None,
                lambda: policy.close() if policy else None,
                lambda: scene.release() if scene else None,
                lambda: wrist.close() if wrist else None,
            ):
                try:
                    fn()
                except Exception:
                    pass
            time.sleep(1)
            main_camera_object.reopen()
            time.sleep(0.3)
            servo_controler.turn_head_to_vla_position(50)
            servo_controler.set_saved_position("default", arm_side="both")

        return "MolmoAct2 arm manipulation done."

    tool_name_to_override.name = tool_name
    tool_name_to_override.description = tool_description

    return tool_name_to_override