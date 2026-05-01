"""Tello movement tools for RoboCrew agents."""

from djitellopy import Tello
from langchain_core.tools import tool  # type: ignore[import]


def create_tello_takeoff(tello: Tello):
    @tool
    def tello_takeoff() -> str:
        """Take off with the Tello drone."""
        tello.takeoff()
        return "Tello took off."

    return tello_takeoff


def create_tello_land(tello: Tello):
    @tool
    def tello_land() -> str:
        """Land the Tello drone."""
        tello.land()
        return "Tello landed."

    return tello_land


def create_tello_move_forward(tello: Tello):
    @tool
    def tello_move_forward(centimeters: int) -> str:
        """Move the Tello forward by the requested number of centimeters."""
        tello.move_forward(int(centimeters))
        return f"Moved forward {centimeters} cm."

    return tello_move_forward


def create_tello_turn_left(tello: Tello):
    @tool
    def tello_turn_left(angle_degrees: int) -> str:
        """Rotate the Tello left by the requested number of degrees."""
        tello.rotate_counter_clockwise(int(angle_degrees))
        return f"Turned left by {angle_degrees} degrees."

    return tello_turn_left


def create_tello_turn_right(tello: Tello):
    @tool
    def tello_turn_right(angle_degrees: int) -> str:
        """Rotate the Tello right by the requested number of degrees."""
        tello.rotate_clockwise(int(angle_degrees))
        return f"Turned right by {angle_degrees} degrees."

    return tello_turn_right
