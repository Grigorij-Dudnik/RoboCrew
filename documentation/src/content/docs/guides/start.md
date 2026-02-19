---
title: How to start
description: How to start using the RoboCrew project.
---

## Quick Start

```bash
pip install robocrew
```

If you want to use voice commands, also run `sudo apt install portaudio19-dev` to install Portaudio for audio support.

(Optional but recommended) Set up **udev rules** for consistent device naming by following the [udev rules guide](../setup/udev-rules), or run the automatic setup script:

```bash
robocrew-setup-usb-modules
```

Then just run the example code below to see your robot in action! Make sure to provide the correct USB ports for your robot's main camera and arm connected to wheels.

### Mobile Robot (XLeRobot)

```python
from robocrew.core.LLMAgent import LLMAgent
from robocrew.core.tools import finish_task
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_left, create_turn_right
from robocrew.robots.XLeRobot.wheel_controls import XLeRobotWheels

# Set up wheels
sdk = XLeRobotWheels.connect_serial("/dev/ttyUSB0")     # provide the right arm usb port - the arm connected to wheels
wheel_controller = XLeRobotWheels(sdk)

# Create movement tools
move_forward = create_move_forward(wheel_controller)
turn_left = create_turn_left(wheel_controller)
turn_right = create_turn_right(wheel_controller)

# Create agent
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    tools=[move_forward, turn_left, turn_right, finish_task],
    main_camera_usb_port="/dev/video0",  # provide usb port main camera connected to
)
agent.task = "Find kitchen in my house and go there."

agent.go()  # Robot explores autonomously
```

