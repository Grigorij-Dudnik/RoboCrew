"""
6_xlerobot_breezyslam_slam.py

LiDAR-only SLAM navigation example using BreezySLAM RMHC_SLAM.
No wheel odometry required — pure scan matching.

Requires BreezySLAM installed:
    cd /home/pi/BreezySLAM/python && python setup.py install

Usage:
    python examples/6_xlerobot_breezyslam_slam.py
"""

import sys
sys.path.insert(0, "src")

from robocrew.core.slam import SlamMapper
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.camera import XLeRobotCamera
from robocrew.robots.XLeRobot.servo_controls import ServoControler
from robocrew.robots.XLeRobot.tools import (
    create_move_forward,
    create_move_backward,
    create_strafe_left,
    create_strafe_right,
    create_turn_left,
    create_turn_right,
    create_look_around,
    create_go_to_precision_mode,
    create_go_to_normal_mode,
)
from robocrew.core.tools import finish_task

# ---------------------------------------------------------------------------
# Hardware
# ---------------------------------------------------------------------------
servo_controler = ServoControler(
    left_arm_head_usb="/dev/left_arm",
    right_arm_usb=None,
)
main_camera = XLeRobotCamera(camera_index=0)

# ---------------------------------------------------------------------------
# SLAM mapper — lidar-only, no odometry
# Loads a previously saved map from ~/.cache/robocrew/slam_map.pkl if present
# ---------------------------------------------------------------------------
slam_mapper = SlamMapper(
    map_size_pixels=500,
    map_size_meters=10,
    load_map=True,
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
## ROBOT SPECS
- Mobile household robot with two arms.

## SENSORS
- Front camera (RGB).
- RPLidar A1: single horizontal plane at ~0.5 m height.
  Obstacles above or below this plane are not detected by LiDAR.
- SLAM occupancy map: built from LiDAR scans only, no odometry.
  Map accumulates across sessions. Robot pose (x, y, heading) is approximate.

## NAVIGATION RULES
- Check the SLAM map BEFORE every move to plan a collision-free path.
- White pixels = free space. Dark pixels = obstacles. Gray = unexplored.
- Red dot on SLAM map = your current position.
- The raw LiDAR scatter view shows the front-distance obstacle warning.
- Align within ±15° before moving forward.
- Use look_around when the target is not visible in the camera.
- Never move forward 3+ times if nothing changes — re-plan instead.
"""

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------
agent = LLMAgent(
    model="google_genai:gemini-2.0-flash",
    system_prompt=SYSTEM_PROMPT,
    tools=[
        create_move_forward(servo_controler),
        create_move_backward(servo_controler),
        create_strafe_left(servo_controler),
        create_strafe_right(servo_controler),
        create_turn_left(servo_controler),
        create_turn_right(servo_controler),
        create_look_around(servo_controler, main_camera),
        create_go_to_precision_mode(servo_controler),
        create_go_to_normal_mode(servo_controler),
        finish_task,
    ],
    history_len=6,
    main_camera=main_camera,
    camera_fov=90,
    servo_controler=servo_controler,
    lidar_usb_port="/dev/lidar",
    slam_mapper=slam_mapper,
)

agent.task = "Explore the environment and build a map of the room. Avoid obstacles."
agent.go()
# SLAM map is saved automatically on shutdown (Ctrl+C)