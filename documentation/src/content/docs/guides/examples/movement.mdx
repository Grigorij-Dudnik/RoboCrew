---
title: Movement Tutorial
description: How to implement basic and advanced movement using RoboCrew.
---

RoboCrew provides pre-built wheel controls and navigation logic for mobile robots like the **XLeRobot** and **Earth Rover**. This tutorial covers how to implement basic and advanced movement.

## 1. Basic Setup

To move a robot, you need to initialize a `ServoControler` (for XLeRobot) or utilize the SDK-based tools (for Earth Rover) and pass them to an `LLMAgent`.

### XLeRobot Example

```python
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_right, create_turn_left
from robocrew.robots.XLeRobot.servo_controls import ServoControler
from robocrew.robots.XLeRobot.xlerobot_LLM_agent import XLeRobotAgent

# 1. Initialize Controller (provide your USB port)
servo_controler = ServoControler(right_arm_wheel_usb="/dev/arm_right")

# 2. Create Tools
move_forward = create_move_forward(servo_controler)
turn_right = create_turn_right(servo_controler)

# 3. Initialize Agent
agent = XLeRobotAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[move_forward, turn_right],
    servo_controler=servo_controler,
    # ... other params like main_camera
)

```

## 2. Core Movement Commands

RoboCrew supports several standard movement types through its tool factory functions:

* **Linear Movement**: `move_forward(distance_meters)` and `move_backward(distance_meters)`.
* **Rotation**: `turn_left(angle_degrees)` and `turn_right(angle_degrees)`.
* **Lateral (Holonomic)**: `strafe_left(distance_meters)` and `strafe_right(distance_meters)` (Specific to XLeRobot's wheel configuration).

## 3. Navigation Modes

XLeRobot supports two distinct navigation modes that change how the robot "sees" its environment while moving:

* **Normal Mode**: Used for long-distance navigation (0.5m – 3m). The camera looks forward at the horizon to identify distant targets.
* **Precision Mode**: Used for close-range movement (0.1m – 0.3m) and manipulation. The camera tilts downward so the agent can see its own body, arm reach boundaries (green lines), and obstacles immediately in front of it.

## 4. Movement Best Practices

To ensure reliable physical movement, the system follows specific logic in its prompts and core code:

* **Spatial Centering**: Targets should be within **±15° to ±20°** of the center (checked via an augmented angle grid overlay) before moving forward.
* **Anti-Stuck Logic**: If the robot calls `move_forward` multiple times without visual change, it is considered "stuck." The agent is instructed to switch to **Precision Mode** and use `move_backward` or `strafe` to clear the obstacle.
* **Look Around**: Use the `look_around` tool if a target is not visible. This rotates the head/camera to capture a 360° panorama (Left, Left-Center, Right-Center, Right) instead of moving blindly.
* **LiDAR Support**: If a LiDAR sensor is connected, the agent receives real-time distance data to the nearest obstacle and a top-down red-marked obstacle map.