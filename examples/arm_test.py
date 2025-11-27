from lerobot.async_inference.robot_client import RobotClient 
from lerobot.async_inference.configs import RobotClientConfig
from lerobot.robots.so101_follower.config_so101_follower import SO101FollowerConfig
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
import threading


def create_vla_arm_manipulation(
        server_address: str,
        policy_name: str, 
        policy_type: str, 
        arm_port: str, 
        camera_config: dict[str, dict], 
        policy_device: str = "cpu"
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
    )

    cfg = RobotClientConfig(
        robot=robot_config,
        task="dummy",
        server_address=server_address,
        policy_type=policy_type,
        pretrained_name_or_path=policy_name,
        policy_device=policy_device,
        actions_per_chunk=50,
        chunk_size_threshold=0.5,
        debug_visualize_queue_size=True,    # probably we need to remove that line, default is false
        fps=30
    )
    
    def grab_cup() -> str:
        """Makes the robot pick up a cup using its arm."""

        client = RobotClient(cfg)
        if not client.start():
           return "Failed to connect to robot server."

        # 3. Start background thread to listen for actions (Required)
        threading.Thread(target=client.receive_actions, daemon=True).start()

        # 4. Schedule the STOP command after 30 seconds
        # This is the key: When this fires, control_loop stops cleanly
        threading.Timer(30.0, client.stop).start()

        # 5. Run the loop
        # This blocks for 30s, then exits automatically when the Timer calls client.stop()
        client.control_loop(task="dummy")


        return "Grabbed a cup."

    return grab_cup


pick_up_cup = create_vla_arm_manipulation(
    "10.57.185.243:8080",
    "Grigorij/act_xle_cup_to_box",
    "act",
    "/dev/arm_right",
    camera_config={"main": {"index_or_path": "/dev/video0"}, "left_arm": {"index_or_path": "/dev/video2"}}, 
)

pick_up_cup()
