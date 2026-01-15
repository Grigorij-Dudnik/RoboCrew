"""Earth Rover basic movement tools with real SDK API implementations."""

import threading
from langchain_core.tools import tool  # type: ignore[import]
import requests
import time
from concurrent.futures import ThreadPoolExecutor


EARTH_ROVER_SDK_URL = "http://127.0.0.1:8000"

@tool
def move_forward(distance_meters: float) -> str:
    """Drives the Earth Rover forward for a specific distance."""
    num_requests = max(1, int(distance_meters / 0.5))   # 0.5 meters per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 1, "angular": 0}})).start()
        time.sleep(0.4)

    return f"Moved forward {distance_meters:.2f} meters."


@tool
def move_backward(distance_meters: float) -> str:
    """Drives the Earth Rover backward for a specific distance."""
    num_requests = max(1, int(distance_meters / 0.5))

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": -1, "angular": 0}})).start()
        time.sleep(0.4)

    return f"Moved backward {distance_meters:.2f} meters."

@tool
def turn_right(angle_degrees: float) -> str:
    """Turns the Earth Rover right by a specified angle in degrees."""
    num_requests = max(1, int(angle_degrees / 25))  # 25 degrees per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0, "angular": -1}})).start()
        time.sleep(0.4)

    return f"Turned right by {angle_degrees:.2f} degrees."   

@tool
def turn_left(angle_degrees: float) -> str:
    """Turns the Earth Rover left by a specified angle in degrees."""
    num_requests = max(1, int(angle_degrees / 25))  # 25 degrees per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0, "angular": 1}})).start()
        time.sleep(0.4)

    return f"Turned left by {angle_degrees:.2f} degrees."   

@tool
def go_forward_with_turning_right(distance_meters: float) -> str:
    """Moves the Earth Rover forward while turning right for a specific distance."""
    num_requests = max(1, int(distance_meters / 0.5))   # 0.5 meters per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 1, "angular": -0.25}})).start()
        time.sleep(0.4)

    return f"Moved forward with turning right for {distance_meters:.2f} meters."

@tool
def go_forward_with_turning_left(distance_meters: float) -> str:
    """Moves the Earth Rover forward while turning left for a specific distance."""
    num_requests = max(1, int(distance_meters / 0.5))   # 0.5 meters per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 1, "angular": 0.25}})).start()
        time.sleep(0.4)

    return f"Moved forward with turning left for {distance_meters:.2f} meters."