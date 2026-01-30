"""Earth Rover basic movement tools with real SDK API implementations."""

import threading
from langchain_core.tools import tool  # type: ignore[import]
import requests
import time
from concurrent.futures import ThreadPoolExecutor


EARTH_ROVER_SDK_URL = "http://127.0.0.1:8000"
LAMP = 0    # 0 or 1 to disable or enable lamps


@tool
def move_forward(distance_meters: float) -> str:
    """Drives the Earth Rover forward for a specific distance."""
    num_requests = max(1, int(distance_meters / 0.32))   # 0.32 meters per request

    for _ in range(num_requests):
        print(time.time())
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 1, "angular": 0, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(0.6)

    return f"Moved forward {distance_meters:.2f} meters."

@tool
def move_forward_carefully(distance_meters: float) -> str:
    """Drives the Earth Rover forward on half of speed. Use when going through rough terrain or when you close to the obstacles."""
    num_requests = max(1, int(distance_meters / 0.32))   # 0.32 meters per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0.5, "angular": 0, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(0.7)

    return f"Moved forward {distance_meters:.2f} meters."

@tool
def move_backward(distance_meters: float) -> str:
    """Drives the Earth Rover backward for a specific distance."""
    num_requests = max(1, int(distance_meters / 0.4))

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": -1, "angular": 0, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(0.5)
    return f"Moved backward {distance_meters:.2f} meters."

@tool
def turn_right(angle_degrees: float) -> str:
    """Turns the Earth Rover right by a specified angle in degrees."""
    num_requests = max(1, int(angle_degrees / 17))  # 17 degrees per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0, "angular": -1, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)

    return f"Turned right by {angle_degrees:.2f} degrees."   

@tool
def turn_left(angle_degrees: float) -> str:
    """Turns the Earth Rover left by a specified angle in degrees."""
    num_requests = max(1, int(angle_degrees / 17))  # 17 degrees per request

    for _ in range(num_requests):
        threading.Thread(target=lambda: requests.post(f"{EARTH_ROVER_SDK_URL}/control", json={"command": {"linear": 0, "angular": 1, "lamp": LAMP}})).start()
        time.sleep(0.4)
    time.sleep(1)

    return f"Turned left by {angle_degrees:.2f} degrees."   
