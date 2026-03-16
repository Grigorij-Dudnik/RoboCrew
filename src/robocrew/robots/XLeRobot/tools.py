import base64
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
from gr00t.policy.server_client import PolicyClient
from robocrew.core.utils import stop_listening_during_tool_execution
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
    robot_config.calibration_dir = None

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

        #assign main camera back to agent
        time.sleep(0.5)
        main_camera_object.reopen()
    
    @tool
    def tool_name_to_override() -> str:
        """Tool description to override."""
        print("Manipulation tool activated")
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


def _groot_recursive_add_extra_dim(obs: dict) -> dict:
    """Add one (batch or time) dimension to every leaf in the obs dict recursively."""
    for key, val in obs.items():
        if isinstance(val, np.ndarray):
            obs[key] = val[np.newaxis, ...]
        elif isinstance(val, dict):
            obs[key] = _groot_recursive_add_extra_dim(val)
        else:
            obs[key] = [val]  # scalar / string -> list
    return obs


def _groot_build_observation(frame1_rgb, frame2_rgb, state_rad, task_prompt: str) -> dict:
    """Convert raw sensor data into the nested dict GR00T policy server expects.

    Camera keys must match those in modality.json (camera1, camera2).
    State is split into single_arm (5 joints) and gripper (1 joint).
    All arrays get (B=1, T=1) dims via two recursive calls.
    """
    obs = {
        "video": {
            "camera1": frame1_rgb,                       # (H, W, 3)  uint8
            "camera2": frame2_rgb,                       # (H, W, 3)  uint8
        },
        "state": {
            "single_arm": state_rad[:5].astype(np.float32),  # (5,)
            "gripper":    state_rad[5:6].astype(np.float32), # (1,)
        },
        "language": {
            "annotation.human.task_description": task_prompt,
        },
    }
    obs = _groot_recursive_add_extra_dim(obs)  # -> (1, ...)
    obs = _groot_recursive_add_extra_dim(obs)  # -> (1, 1, ...)
    return obs


def _groot_decode_action_chunk(chunk: dict, t: int, motor_ids: list) -> dict:
    """Extract timestep t from action chunk dict and map to {motor_id: degrees}.

    chunk["single_arm"]: (B, T, 5)  radians
    chunk["gripper"]:    (B, T, 1)  radians
    Returns: {motor_id: float_degrees}
    """
    single_arm = chunk["single_arm"][0][t]  # (5,)
    gripper    = chunk["gripper"][0][t]      # (1,)
    full_rad   = np.concatenate([single_arm, gripper], axis=0)  # (6,)
    return {
        mid: math.degrees(float(full_rad[i]))
        for i, mid in enumerate(motor_ids)
    }


def create_groot_single_arm_manipulation(
        tool_name: str,
        tool_description: str,
        task_prompt: str,
        server_host: str,
        server_port: int,
        arm_port: str,
        motor_ids: list,
        camera1_index_or_path,
        camera2_index_or_path,
        camera_width: int,
        camera_height: int,
        main_camera_object,
        servo_controller,
        execution_time: int = 30,
        fps: int = 30,
        timeout_ms: int = 15000,
    ):
    """Creates a LangChain tool that runs a GR00T policy for single-arm manipulation.

    Args:
        tool_name (str): The name of the tool the AI agent will see.
        tool_description (str): The description of the tool the AI agent will see.
        task_prompt (str): Natural-language task instruction sent to the GR00T policy.
        server_host (str): Hostname of the running GR00T policy server.
        server_port (int): Port of the GR00T policy server (default 5555).
        arm_port (str): USB device path for the arm's FeetechMotorsBus (e.g. "/dev/arm_right").
        motor_ids (list): Ordered list of motor IDs on the arm (e.g. [1,2,3,4,5,6]).
        camera1_index_or_path: OpenCV index or device path for the primary arm camera.
        camera2_index_or_path: OpenCV index or device path for the secondary/overview camera.
        camera_width (int): Camera capture width in pixels.
        camera_height (int): Camera capture height in pixels.
        main_camera_object: The agent's main camera — released before and restored after execution.
        servo_controller: Robot servo controller used to position the head for manipulation.
        execution_time (int): How long in seconds to run the policy.
        fps (int): Control loop frequency.
        timeout_ms (int): PolicyClient request timeout in milliseconds.
    """

    @tool
    def tool_name_to_override() -> str:
        """Tool description to override."""
        print(f"GR00T manipulation tool activated: {tool_name}")

        servo_controller.turn_head_to_vla_position()
        main_camera_object.release()
        time.sleep(1)

        cap1 = cv2.VideoCapture(camera1_index_or_path)
        cap1.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)

        cap2 = cv2.VideoCapture(camera2_index_or_path)
        cap2.set(cv2.CAP_PROP_FRAME_WIDTH, camera_width)
        cap2.set(cv2.CAP_PROP_FRAME_HEIGHT, camera_height)

        arm_bus = FeetechMotorsBus(
            port=arm_port,
            motors={mid: Motor(mid, "sts3215", MotorNormMode.DEGREES) for mid in motor_ids},
        )
        arm_bus.connect()

        policy = PolicyClient(host=server_host, port=server_port, timeout_ms=timeout_ms)
        if not policy.ping():
            arm_bus.disconnect()
            cap1.release()
            cap2.release()
            time.sleep(1)
            main_camera_object.reopen()
            servo_controller.turn_head_to_vla_position(50)
            return "Failed to connect to GR00T policy server."

        policy.reset()

        dt = 1.0 / fps
        start_time = time.time()

        try:
            while time.time() - start_time < execution_time:
                ret1, frame1 = cap1.read()
                ret2, frame2 = cap2.read()
                if not ret1 or not ret2:
                    break

                frame1_rgb = cv2.cvtColor(frame1, cv2.COLOR_BGR2RGB)
                frame2_rgb = cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB)

                positions_deg = [arm_bus.read("Present_Position", mid) for mid in motor_ids]
                state_rad = np.array(
                    [math.radians(deg) for deg in positions_deg], dtype=np.float32
                )  # (6,)

                obs = _groot_build_observation(frame1_rgb, frame2_rgb, state_rad, task_prompt)

                action_chunk, _ = policy.get_action(obs)
                # action_chunk = {"single_arm": (1, T, 5), "gripper": (1, T, 1)}

                horizon = action_chunk["single_arm"].shape[1]
                for t in range(horizon):
                    if time.time() - start_time >= execution_time:
                        break
                    action_deg = _groot_decode_action_chunk(action_chunk, t, motor_ids)
                    arm_bus.sync_write("Goal_Position", action_deg)
                    time.sleep(dt)

        finally:
            arm_bus.disconnect()
            cap1.release()
            cap2.release()
            time.sleep(1)
            main_camera_object.reopen()
            servo_controller.turn_head_to_vla_position(50)

        return "GR00T arm manipulation done."

    tool_name_to_override.name = tool_name
    tool_name_to_override.description = tool_description

    return tool_name_to_override


def _shutdown_robot_client(client: "RobotClient") -> None:
    """Gracefully stop the control loop before disconnecting the robot.

    Signals the running control loop to exit on its next iteration before
    hardware disconnection, preventing race conditions.
    """
    client.stop()
