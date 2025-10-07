#from smolagents import tool
import sys
from pathlib import Path
from langchain_core.tools import tool  # type: ignore[import]

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root / "connectors" / "XLeRobot"))
from wheel_controls import XLeRobotWheels  # type: ignore[import]


sdk = XLeRobotWheels.connect_serial("/dev/ttyACM1")
wheel_controller = XLeRobotWheels(sdk)


@tool
def move_forward(duration_seconds: float) -> str:
    """Drives the robot forward for a specified duration.

    Args:
        duration_seconds: Number of seconds to keep the wheels in forward motion.
    """

    duration = max(0.0, float(duration_seconds))
    wheel_controller.go_forward(duration)
    return f"Moved forward for {duration:.2f} seconds."


@tool
def turn_right(duration_seconds: float) -> str:
    """Turns the robot right for a specified duration.

    Args:
        duration_seconds: Number of seconds to apply right turn motion.
    """

    duration = max(0.0, float(duration_seconds))
    wheel_controller.turn_right(duration)
    return f"Turned right for {duration:.2f} seconds."


@tool
def turn_left(duration_seconds: float) -> str:
    """Turns the robot left for a specified duration.

    Args:
        duration_seconds: Number of seconds to apply left turn motion.
    """

    duration = max(0.0, float(duration_seconds))
    wheel_controller.turn_left(duration)
    return f"Turned left for {duration:.2f} seconds."
    

@tool
def finish_task():
    """claim that task is finished and go idle."""
    return "Task finished"