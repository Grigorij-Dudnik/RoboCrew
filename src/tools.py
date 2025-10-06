from smolagents import tool
import sys
import os
import json
from pathlib import Path
project_root = Path(__file__).parent.parent
config_path = project_root / "connectors" / "XLeRobot" / "dual_mapper_config.json"
sys.path.append(str(project_root / "connectors" / "XLeRobot"))
from wheel_controls import XLeRobotWheels


sdk = XLeRobotWheels.connect_serial("/dev/ttyACM0")
wheel_conf = json.load(open(config_path, "r"))['portB']['wheel']
wheel_controller = XLeRobotWheels(sdk, wheel_conf)


def move_forward(distance: float) -> str:
    """Moves robot forward using wheel controls.

    Args:
        distance: distance in meters to move (currently not used for speed, just for API compatibility).
    """
    wheel_controller.go_forward()
    return f"Moved forward {distance} meters."


def turn_right(angle: float) -> str:
    """Turns robot right by provided angle using wheel controls.

    Args:
        angle: angle in degrees to turn right.
    """
    wheel_controller.turn_right()
    return f"Turned right by {angle} degrees."


def turn_left(angle: float) -> str:
    """Turns robot left by provided angle using wheel controls.

    Args:
        angle: angle in degrees to turn left.
    """
    wheel_controller.turn_left()
    return f"Turned left by {angle} degrees."


def stop() -> str:
    """Stops all wheels."""
    wheel_controller.stop_wheels()
    return "Stopped all wheels."