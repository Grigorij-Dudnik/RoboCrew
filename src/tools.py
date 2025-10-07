#from smolagents import tool
import sys
from pathlib import Path
from langchain_core.tools import tool  # type: ignore[import]

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "connectors" / "XLeRobot"))
from wheel_controls import XLeRobotWheels  # type: ignore[import]


sdk = XLeRobotWheels.connect_serial("/dev/ttyACM0")
wheel_controller = XLeRobotWheels(sdk)


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