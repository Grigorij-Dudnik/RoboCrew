from smolagents import tool
from langchain_core.tools import tool as lg_tool


@tool
def move_forward(distance: float) -> str:
    """Moves robot forward.

    Args:
        distance: distance in meters to move.
    """
    print(f"Moving forward {distance} meters.")
    return "Moved succesfully"


@tool
def turn(angle: float) -> str:
    """Turns robot by provided angle.

    Args:
        angle: turns robot by provided angle in degrees. Positive angle - turn right, negative - turn left.
    """
    print(f"Turning by {angle} degrees.")
    return f"Turned by {angle} degrees."