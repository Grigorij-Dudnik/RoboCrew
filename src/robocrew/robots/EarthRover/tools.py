"""Earth Rover basic movement tools with real SDK API implementations."""

import threading
from langchain_core.tools import tool  # type: ignore[import]
import requests
import time


EARTH_ROVER_SDK_URL = "http://127.0.0.1:8000"
LAMP = 0    # 0 or 1 to disable or enable lamps


@tool
def move_forward(distance_meters: float) -> str:
    """Drives the Earth Rover forward."""
    num_requests = max(1, int(distance_meters / 0.15))   # 0.15 meters per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0.5, "angular": 0, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)

    return f"Moved forward {distance_meters:.2f} meters."

@tool
def move_backward(distance_meters: float) -> str:
    """Drives the Earth Rover backward for a specific distance."""
    num_requests = max(1, int(distance_meters / 0.15))

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": -0.5, "angular": 0, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)
    return f"Moved backward {distance_meters:.2f} meters."

@tool
def move_forward_max_speed(distance_meters: float) -> str:
    """Boosts the Earth Rover forward at maximum speed. Use only to force obstacles you can't force at normal speed."""
    num_requests = max(1, int(distance_meters / 0.34))   # 0.34 meters per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 1, "angular": 0, "lamp": LAMP}})).start()
        time.sleep(0.4)
    # slow down on the end of movement to stabilize Earth accels measurement
    threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0.6, "angular": 0, "lamp": LAMP}})).start()
    time.sleep(0.4)
    threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0.3, "angular": 0, "lamp": LAMP}})).start()
    time.sleep(0.4)
    # time to finish movement, stabilize before Earth accels measurement
    time.sleep(1)

    return f"Moved forward {distance_meters:.2f} meters."


@tool
def turn_right_forward_rotation(angle_degrees: float) -> str:
    """Turns the Earth Rover right by a specified angle in degrees with small movement forward."""
    num_requests = max(1, int(angle_degrees / 17))  # 17 degrees per request
    
    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0.2, "angular": -1, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)

    return f"Turned right by {angle_degrees:.2f} degrees."   

@tool
def turn_left_forward_rotation(angle_degrees: float) -> str:
    """Turns the Earth Rover left by a specified angle in degrees with small movement forward."""
    num_requests = max(1, int(angle_degrees / 17))  # 17 degrees per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0.2, "angular": 1, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)

    return f"Turned left by {angle_degrees:.2f} degrees."   

@tool
def turn_right_backward_rotation(angle_degrees: float) -> str:
    """Turns the Earth Rover right by a specified angle in degrees with small movement backward."""
    num_requests = max(1, int(angle_degrees / 17))  # 17 degrees per request
    
    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": -0.2, "angular": -1, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)

    return f"Turned right by {angle_degrees:.2f} degrees."

@tool
def turn_left_backward_rotation(angle_degrees: float) -> str:
    """Turns the Earth Rover left by a specified angle in degrees with small movement backward."""
    num_requests = max(1, int(angle_degrees / 17))  # 17 degrees per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": -0.2, "angular": 1, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)

    return f"Turned left by {angle_degrees:.2f} degrees."