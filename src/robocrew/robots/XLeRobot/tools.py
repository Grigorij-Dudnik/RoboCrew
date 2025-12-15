import base64
import cv2
from pathlib import Path
from langchain_core.tools import tool  # type: ignore[import]
from lerobot.async_inference.robot_client import RobotClient 
from lerobot.async_inference.configs import RobotClientConfig
from lerobot.robots.so101_follower.config_so101_follower import SO101FollowerConfig
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
        """Turns the robot left by angle in degrees."""
        angle = float(angle_degrees)
        servo_controller.turn_left(angle)
        time.sleep(0.4)  # wait a bit after turn for stabilization
        return f"Turned left by {angle} degrees."

    return turn_left

def create_look_around(servo_controller, main_camera):
    @tool
    def look_around() -> list:
        """Look around yourself to find a thing you looking for or to understand an envinronment."""
        movement_delay = 1.5  # seconds
        print("Looking around...")
        servo_controller.turn_head_yaw(-120)
        time.sleep(movement_delay)
        image_left = capture_image(main_camera, center_angle=-120)
        image_left64 = base64.b64encode(image_left).decode('utf-8')
        servo_controller.turn_head_yaw(120)
        time.sleep(movement_delay)
        image_right = capture_image(main_camera, center_angle=120)
        image_right64 = base64.b64encode(image_right).decode('utf-8')  
        servo_controller.turn_head_yaw(0)
        time.sleep(movement_delay)
        image_center = capture_image(main_camera)
        image_center64 = base64.b64encode(image_center).decode('utf-8')

        return "Looked around", [
            {"type": "text", "text": "Left"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_left64}",}},
            {"type": "text", "text": "Center"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_center64}"}},
            {"type": "text", "text": "Right"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_right64}"}},         
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
        servo_controller, 
        camera_config: dict[str, dict], 
        main_camera_object,
        main_camera_usb_port: str,
        execution_time: int = 30,
        policy_device: str = "cuda"

    ):
    """Creates a tool that makes the robot pick up a cup using its arm.
    Args:
        server_address (str): The address of the server to connect to.
        policy_name (str): The name or path of the pretrained policy.
        policy_type (str): The type of policy to use.
        arm_port (str): The USB port of the robot's arm.
        camera_config (dict, optional): Lerobot-type camera configuration. (E.g., "{ main: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30}, left_arm: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30}}")
        policy_device (str, optional): The device to run the policy on. Defaults to "cuda".
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
        actions_per_chunk=50,
        chunk_size_threshold=0.5,
        fps=30
    )
    
    @tool
    def tool_name_to_override() -> str:
        """Tood description to override."""
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
            main_camera_object.open(main_camera_usb_port)
            main_camera_object.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            servo_controller.reset_head_position()
        
        return "Arm manipulation done"
    
    tool_name_to_override.name = tool_name
    tool_name_to_override.description = tool_description

    return tool_name_to_override
