"""Tello movement tools for RoboCrew agents."""

import time

from djitellopy import Tello
from langchain_core.tools import tool  # type: ignore[import]

RC_VELOCITY = 20
RC_TICK_SECONDS = 0.1

def _rc_move(tello: Tello, centimeters: int, rc_values: tuple[int, int, int, int]) -> None:
    duration = abs(int(centimeters)) / RC_VELOCITY
    elapsed = 0.0

    tello.set_speed(RC_VELOCITY)

    try:
        while elapsed < duration:
            tello.send_rc_control(*rc_values)
            time.sleep(RC_TICK_SECONDS)
            elapsed += RC_TICK_SECONDS
    finally:
        tello.send_rc_control(0, 0, 0, 0)


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
        """Move the Tello forward by 20-150 centimeters."""
        _rc_move(tello, int(centimeters), (0, RC_VELOCITY, 0, 0))
        return f"Moved forward about {centimeters} cm."

    return move_forward


def create_move_backward(tello: Tello):
    @tool
    def move_backward(centimeters: int) -> str:
        """Move the Tello backward by 20-50 centimeters."""
        _rc_move(tello, int(centimeters), (0, -RC_VELOCITY, 0, 0))
        return f"Moved backward about {centimeters} cm."

    return move_backward


def create_move_up(tello: Tello):
    @tool
    def move_up(centimeters: int) -> str:
        """Move the Tello up by 20-70 centimeters."""
        _rc_move(tello, int(centimeters), (0, 0, RC_VELOCITY, 0))
        return f"Moved up about {centimeters} cm."

    return move_up


def create_move_down(tello: Tello):
    @tool
    def move_down(centimeters: int) -> str:
        """Move the Tello down by 20-70 centimeters."""
        _rc_move(tello, int(centimeters), (0, 0, -RC_VELOCITY, 0))
        return f"Moved down about {centimeters} cm."

    return move_down


def create_strafe_left(tello: Tello):
    @tool
    def strafe_left(centimeters: int) -> str:
        """Move the Tello left by 20-50 centimeters."""
        _rc_move(tello, int(centimeters), (-RC_VELOCITY, 0, 0, 0))
        return f"Moved left about {centimeters} cm."

    return strafe_left


def create_strafe_right(tello: Tello):
    @tool
    def strafe_right(centimeters: int) -> str:
        """Move the Tello right by 20-50 centimeters."""
        _rc_move(tello, int(centimeters), (RC_VELOCITY, 0, 0, 0))
        return f"Moved right about {centimeters} cm."

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
