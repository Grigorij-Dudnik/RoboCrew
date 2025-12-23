import base64
from langchain_core.tools import tool  # type: ignore[import]
from lerobot.async_inference.robot_client import RobotClient 
from lerobot.async_inference.configs import RobotClientConfig
from lerobot.robots.so101_follower.config_so101_follower import SO101FollowerConfig
from lerobot.robots.bi_so100_follower.config_bi_so100_follower import BiSO100FollowerConfig
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
from robocrew.core.utils import capture_image
import time
import threading


def create_move_forward(servo_controller):
    @tool
    def move_forward(distance_meters: float) -> str:
        """Drives the robot forward (or backward) for a specific distance."""

        distance = float(distance_meters)
        if distance >= 0:
            servo_controller.go_forward(distance)
        else:
            servo_controller.go_backward(-distance)
        return f"Moved {'forward' if distance >= 0 else 'backward'} {abs(distance):.2f} meters."

    return move_forward

def create_move_backward(servo_controller):
    @tool
    def move_backward(distance_meters: float) -> str:
        """Drives the robot forward (or backward) for a specific distance."""

        distance = float(distance_meters)
        servo_controller.go_backward(distance)
        return f"Moved backward {distance} meters."

    return move_backward

def create_turn_right(servo_controller):
    @tool
    def turn_right(angle_degrees: float) -> str:
        """Turns the robot right by angle in degrees."""
        angle = float(angle_degrees)
        servo_controller.turn_right(angle)
        time.sleep(0.4)  # wait a bit after turn for stabilization
        return f"Turned right by {angle} degrees."

    return turn_right

def create_turn_left(servo_controller):
    @tool
    def turn_left(angle_degrees: float) -> str:
        """Turns the robot left by angle in degrees. Use only when robot body not toches any obstacle."""
        angle = float(angle_degrees)
        servo_controller.turn_left(angle)
        time.sleep(0.4)  # wait a bit after turn for stabilization
        return f"Turned left by {angle} degrees."

    return turn_left


def create_strafe_left(servo_controller):
    @tool
    def strafe_left(distance_meters: float) -> str:
        """Moves the robot sideways left by a specific distance in meters."""
        distance = float(distance_meters)
        servo_controller.strafe_left(distance)
        return f"Strafed left by {distance} meters."

    return strafe_left

def create_strafe_right(servo_controller):
    @tool
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
        image_1 = capture_image(main_camera.capture, center_angle=-120)
        image_1_64 = base64.b64encode(image_1).decode('utf-8')
        servo_controller.turn_head_yaw(-40)
        time.sleep(movement_delay)
        image_2 = capture_image(main_camera.capture, center_angle=-40)
        image_2_64 = base64.b64encode(image_2).decode('utf-8')  
        servo_controller.turn_head_yaw(40)
        time.sleep(movement_delay)
        image_3 = capture_image(main_camera.capture, center_angle=40)
        image_3_64 = base64.b64encode(image_3).decode('utf-8')
        servo_controller.turn_head_yaw(120)
        time.sleep(movement_delay)
        image_4 = capture_image(main_camera.capture, center_angle=120)
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


    robot_config = SO101FollowerConfig(
        port=arm_port,
        cameras=configured_cameras,
        id="robot_arms",
        # TODO: Figure out calibration loading/saving issues
        # calibration_dir=Path("/home/pi/RoboCrew/calibrations")
    )

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
    
    @tool
    def tool_name_to_override() -> str:
        """Tool description to override."""
        print("Manipulation tool activated")
        servo_controler.turn_head_pitch(45)
        servo_controler.turn_head_yaw(0)
        # release main camera from agent, so arm policy can use it
        main_camera_object.release()
        time.sleep(1)  # give some time to release camera

        try:
            client = RobotClient(cfg)
            if not client.start():
                return "Failed to connect to robot server."

            threading.Thread(target=client.receive_actions, daemon=True).start()
            threading.Timer(execution_time, client.stop).start()
            client.control_loop(task=task_prompt)
            
        
        finally:
            # Re-open main camera for agent use. 
            time.sleep(1)
            main_camera_object.reopen()
            servo_controler.reset_head_position()
        
        return "Arm manipulation done"
    
    tool_name_to_override.name = tool_name
    tool_name_to_override.description = tool_description

    return tool_name_to_override


def create_vla_two_arm_manipulation(
        tool_name: str,
        tool_description: str,
        task_prompt: str,
        server_address: str,
        policy_name: str, 
        policy_type: str, 
        servo_controller, 
        camera_config: dict[str, dict], 
        main_camera_object,
        execution_time: int = 30,
        policy_device: str = "cuda",
        fps: int = 30,
        actions_per_chunk: int = 50,
    ):
    """Creates a tool that makes the robot pick up a cup using its arm.
    Args:
        tool_name (str): The name of the tool AI agent will see.
        tool_description (str): The description of the tool AI agent will see.
        task_prompt (str): The task prompt to give to the VLA policy.
        server_address (str): The address of the server to connect to.
        policy_name (str): The name or path of the pretrained policy.
        policy_type (str): The type of policy to use.
        camera_config (dict, optional): Lerobot-type camera configuration. (E.g., "{ main: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30}, left_arm: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30}}")
        execution_time (int, optional): Time in seconds to run the manipulation.
        policy_device (str, optional): The device to run the policy on. Defaults to "cuda".
        fps (int, optional): The fps to run the policy at.
        actions_per_chunk (int, optional): Number of actions VLA calculates at once.
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


    robot_config = BiSO100FollowerConfig(
        left_arm_port=servo_controller.left_arm_head_usb,
        right_arm_port=servo_controller.right_arm_wheel_usb,
        cameras=configured_cameras,
        id="robot_arms",
    )

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
    
    @tool
    def tool_name_to_override() -> str:
        """Tool description to override."""
        print("Manipulation tool activated")
        servo_controller.turn_head_pitch(45)
        servo_controller.turn_head_yaw(0)
        # release main camera from agent, so arm policy can use it
        main_camera_object.release()
        time.sleep(1)  # give some time to release camera

        try:
            client = RobotClient(cfg)
            if not client.start():
                return "Failed to connect to robot server."

            threading.Thread(target=client.receive_actions, daemon=True).start()
            threading.Timer(execution_time, client.stop).start()
            client.control_loop(task=task_prompt)
            
        
        finally:
            # Re-open main camera for agent use. 
            time.sleep(1)
            main_camera_object.reopen()
            servo_controller.reset_head_position()
        
        return "Arm manipulation done"
    
    tool_name_to_override.name = tool_name
    tool_name_to_override.description = tool_description

    return tool_name_to_override
