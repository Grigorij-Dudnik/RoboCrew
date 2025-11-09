import base64
import sys
from pathlib import Path
from langchain_core.tools import tool  # type: ignore[import]
import time


def create_move_forward(wheel_controller):
    @tool
    def move_forward(distance_meters: float) -> str:
        """Drives the robot forward (or backward) for a specific distance."""

        distance = float(distance_meters)
        if distance >= 0:
            wheel_controller.go_forward(distance)
        else:
            wheel_controller.go_backward(-distance)
        return f"Moved {'forward' if distance >= 0 else 'backward'} {abs(distance):.2f} meters."

    return move_forward


def create_turn_right(wheel_controller):
    @tool
    def turn_right(angle_degrees: float) -> str:
        """Turns the robot right by angle in degrees."""
        angle = float(angle_degrees)
        wheel_controller.turn_right(angle)
        time.sleep(0.4)  # wait a bit after turn for stabilization
        return f"Turned right by {angle} degrees."

    return turn_right


def create_turn_left(wheel_controller):
    @tool
    def turn_left(angle_degrees: float) -> str:
        """Turns the robot left by angle in degrees."""
        angle = float(angle_degrees)
        wheel_controller.turn_left(angle)
        time.sleep(0.4)  # wait a bit after turn for stabilization
        return f"Turned left by {angle} degrees."

    return turn_left

def create_look_around(head_controller, main_camera):
    @tool
    def look_around() -> str:
        """Makes the robot look around by moving its head."""
        head_controller.turn_head_yaw(-45)
        image_left = main_camera.capture_image()
        image_left64 = base64.b64encode(image_left).decode('utf-8')
        time.sleep(1)
        head_controller.turn_head_yaw(45)
        image_right = main_camera.capture_image()
        image_right64 = base64.b64encode(image_right).decode('utf-8')  
        time.sleep(1)
        head_controller.turn_head_yaw(0)
        image_center = main_camera.capture_image()
        image_center64 = base64.b64encode(image_center).decode('utf-8')
        return f"Looked around and captured images: left (data:image/jpeg;base64,{image_left64}), center (data:image/jpeg;base64,{image_center64}), right (data:image/jpeg;base64,{image_right64})."

    return look_around
