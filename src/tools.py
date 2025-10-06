from smolagents import tool
import sys
import os
import json
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'connectors', 'XLeRobot')))
from wheel_controls import XLeRobotWheels


sdk = XLeRobotWheels.connect_serial("/dev/ttyACM0")
wheel_conf = json.load(open("../connectors/XLeRobot/dual_mapper_config.json", "r"))['portB']['wheel']
wheel_controller = XLeRobotWheels(sdk, wheel_conf)

@tool
def move_forward(distance: float) -> str:
    """Moves robot forward using wheel controls.

    Args:
        distance: distance in meters to move (currently not used for speed, just for API compatibility).
    """
    wheel_controller.go_forward()
    return f"Moved forward {distance} meters."


@tool
def turn_right(angle: float) -> str:
    """Turns robot right by provided angle using wheel controls.

    Args:
        angle: angle in degrees to turn right.
    """
    wheel_controller.turn_right()
    return f"Turned right by {angle} degrees."


@tool
def turn_left(angle: float) -> str:
    """Turns robot left by provided angle using wheel controls.

    Args:
        angle: angle in degrees to turn left.
    """
    wheel_controller.turn_left()
    return f"Turned left by {angle} degrees."

@tool
def stop() -> str:
    """Stops all wheels."""
    wheel_controller.stop_wheels()
    return "Stopped all wheels."