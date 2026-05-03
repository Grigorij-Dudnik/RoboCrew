"""Tello movement tools for RoboCrew agents."""

from djitellopy import Tello
from langchain_core.tools import tool  # type: ignore[import]


def create_takeoff(tello: Tello):
    @tool
    def takeoff() -> str:
        """Take off with the Tello drone."""
        tello.takeoff()
        return "Tello took off."

    return takeoff


def create_land(tello: Tello):
    @tool
    def land() -> str:
        """Land the Tello drone."""
        tello.land()
        return "Tello landed."

    return land


def create_move_forward(tello: Tello):
    @tool
    def move_forward(centimeters: int) -> str:
        """Move the Tello forward by the requested number of centimeters (only positive)."""
        tello.move_forward(int(centimeters))
        return f"Moved forward {centimeters} cm."

    return move_forward


def create_move_up(tello: Tello):
    @tool
    def move_up(centimeters: int) -> str:
        """Move the Tello up by the requested number of centimeters."""
        tello.move_up(int(centimeters))
        return f"Moved up {centimeters} cm."

    return move_up


def create_move_down(tello: Tello):
    @tool
    def move_down(centimeters: int) -> str:
        """Move the Tello down by the requested number of centimeters."""
        tello.move_down(int(centimeters))
        return f"Moved down {centimeters} cm."

    return move_down


def create_strafe_left(tello: Tello):
    @tool
    def strafe_left(centimeters: int) -> str:
        """Move the Tello left by the requested number of centimeters."""
        tello.move_left(int(centimeters))
        return f"Moved left {centimeters} cm."

    return strafe_left


def create_strafe_right(tello: Tello):
    @tool
    def strafe_right(centimeters: int) -> str:
        """Move the Tello right by the requested number of centimeters."""
        tello.move_right(int(centimeters))
        return f"Moved right {centimeters} cm."

    return strafe_right


def create_turn_left(tello: Tello):
    @tool
    def turn_left(angle_degrees: int) -> str:
        """Rotate the Tello left by the requested number of degrees."""
        tello.rotate_counter_clockwise(int(angle_degrees))
        return f"Turned left by {angle_degrees} degrees."

    return turn_left


def create_turn_right(tello: Tello):
    @tool
    def turn_right(angle_degrees: int) -> str:
        """Rotate the Tello right by the requested number of degrees."""
        tello.rotate_clockwise(int(angle_degrees))
        return f"Turned right by {angle_degrees} degrees."

    return turn_right
