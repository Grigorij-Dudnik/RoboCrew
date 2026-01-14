"""Earth Rover basic movement tools with real SDK API implementations."""

from langchain_core.tools import tool  # type: ignore[import]
import requests
import time

# Default Earth Rover SDK URL
EARTH_ROVER_SDK_URL = "http://localhost:8000"

@tool
def move_forward(distance_meters: float) -> str:
    """Drives the Earth Rover forward for a specific distance."""
    distance = float(distance_meters)
    num_requests = max(1, int(distance / 0.5))
    
    for i in range(num_requests):
        # Send forward movement command (0.5m per request)
        requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0.5}},
            headers={"Content-Type": "application/json"}
        ) 
    
    return f"Moved forward {distance:.2f} meters."



@tool
def move_backward(distance_meters: float) -> str:
    """Drives the Earth Rover backward for a specific distance."""
    distance = float(distance_meters)
    
    try:
        # Earth Rover SDK uses distance-based commands (max 0.5m per request)
        # Send multiple requests for distances > 0.5m
        total_distance = 0.0
        remaining_distance = distance
        
        while remaining_distance > 0:
            # Calculate distance for this request (max 0.5m)
            request_distance = min(0.5, remaining_distance)
            
            # Send backward movement command (negative distance)
            response = requests.post(
                f"{EARTH_ROVER_SDK_URL}/control",
                json={"command": {"linear": -request_distance, "angular": 0}},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            total_distance += request_distance
            remaining_distance -= request_distance
            
            # Small delay between requests
            time.sleep(0.1)
        
        return f"Moved backward {total_distance:.2f} meters."
        
    except requests.RequestException as e:
        return f"Error moving backward: {e}"

@tool
def turn_right(angle_degrees: float) -> str:
    """Turns the Earth Rover right by a specified angle in degrees."""
    angle = float(angle_degrees)
    
    # Calculate turn duration (adjust multiplier as needed)
    duration = max(0.3, min(2.0, angle * 0.02))  # 0.02s per degree, min 0.3s, max 2s
    
    try:
        # Send right turn command
        response = requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0, "angular": 0.5}},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        # Wait for turn to complete
        time.sleep(duration)
        
        # Send stop command
        requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0, "angular": 0}},
            headers={"Content-Type": "application/json"}
        )
        
        return f"Turned right by {angle} degrees."
        
    except requests.RequestException as e:
        return f"Error turning right: {e}"

@tool
def turn_left(angle_degrees: float) -> str:
    """Turns the Earth Rover left by a specified angle in degrees."""
    angle = float(angle_degrees)
    
    # Calculate turn duration
    duration = max(0.3, min(2.0, angle * 0.02))
    
    try:
        # Send left turn command
        response = requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0, "angular": -0.5}},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        # Wait for turn to complete
        time.sleep(duration)
        
        # Send stop command
        requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0, "angular": 0}},
            headers={"Content-Type": "application/json"}
        )
        
        return f"Turned left by {angle} degrees."
        
    except requests.RequestException as e:
        return f"Error turning left: {e}"

@tool
def go_forward_with_turning_right(distance_meters: float) -> str:
    """Moves the Earth Rover forward while turning right for a specific distance."""
    distance = float(distance_meters)
    
    # Calculate movement duration
    duration = max(0.5, min(3.0, distance * 0.5))
    
    try:
        # Send forward + right turn command
        response = requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0.5, "angular": 0.3}},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        # Wait for movement to complete
        time.sleep(duration)
        
        # Send stop command
        requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0, "angular": 0}},
            headers={"Content-Type": "application/json"}
        )
        
        return f"Moved forward {distance:.2f} meters while turning right."
        
    except requests.RequestException as e:
        return f"Error moving forward with right turn: {e}"

@tool
def go_forward_with_turning_left(distance_meters: float) -> str:
    """Moves the Earth Rover forward while turning left for a specific distance."""
    distance = float(distance_meters)
    
    # Calculate movement duration
    duration = max(0.5, min(3.0, distance * 0.5))
    
    try:
        # Send forward + left turn command
        response = requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0.5, "angular": -0.3}},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        # Wait for movement to complete
        time.sleep(duration)
        
        # Send stop command
        requests.post(
            f"{EARTH_ROVER_SDK_URL}/control",
            json={"command": {"linear": 0, "angular": 0}},
            headers={"Content-Type": "application/json"}
        )
        
        return f"Moved forward {distance:.2f} meters while turning left."
        
    except requests.RequestException as e:
        return f"Error moving forward with left turn: {e}"