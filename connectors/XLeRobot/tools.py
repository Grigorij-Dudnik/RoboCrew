#from smolagents import tool
import sys
from pathlib import Path
from langchain_core.tools import tool  # type: ignore[import]

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))
from connectors.XLeRobot.wheel_controls import XLeRobotWheels


sdk = XLeRobotWheels.connect_serial("/dev/arm_right")
wheel_controller = XLeRobotWheels(sdk)


@tool
def move_forward(distance_meters: float) -> str:
    """Drives the robot forward (or backward) for a specific distance."""

    distance = float(distance_meters)
    if distance >= 0:
        wheel_controller.go_forward(distance)
    else:
        wheel_controller.go_backward(-distance)
    return f"Moved {'forward' if distance >= 0 else 'backward'} {abs(distance):.2f} meters."


@tool
def turn_right(angle_degrees: float) -> str:
    """Turns the robot right (or left if negative) by a specific angle in degrees."""

    angle = float(angle_degrees)
    if angle >= 0:
        wheel_controller.turn_right(angle)
    else:
        wheel_controller.turn_left(-angle)
    return f"Turned {'right' if angle >= 0 else 'left'} by {abs(angle):.2f} degrees."


@tool
def turn_left(angle_degrees: float) -> str:
    """Turns the robot left (or right if negative) by a specific angle in degrees."""
    angle = float(angle_degrees)
    if angle >= 0:
        wheel_controller.turn_left(angle)
    else:
        wheel_controller.turn_right(-angle)
    return f"Turned {'left' if angle >= 0 else 'right'} by {abs(angle):.2f} degrees."
