# 🤖 RoboCrew

**Build AI-powered robots that see, move, and manipulate objects — in a few lines of code.**

RoboCrew makes it stupidly simple to create LLM agents for physical robots. Think of it like building agents with CrewAI or AutoGen, except your agents live in the real world with cameras, microphones, wheels, and arms.

![xlerobot_schema](https://github.com/user-attachments/assets/d371487c-2e77-4a3e-9f20-eb6a54e427af)


## Features

- 👁️ **Vision** - Camera feed with automatic angle grid overlay for spatial understanding
- 🎤 **Voice** - Wake-word activated voice commands
- 🧠 **Intelligence** - LLM agent robot control provides complete autonomy and decision making
- 🚗 **Movement** - Pre-built wheel controls for mobile robots
- 📚 **Memory** - Long-term memory to remember envinronment details
- 🦾 **Manipulation** - VLA models as a tools for arms control
- 🗺️ **Navigation** - Navigation features

## Supported Robots

- **XLeRobot**
- **LeKiwi** (not tested, but we assume XLeRobot code will work for it as platforms are similar. Please try to run repo on your LeKiwi and open an issue with info if it works)
- More robot platforms coming soon!


## Quick Start

```bash
pip install robocrew
```

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

### With Voice Commands

Add a microphone to give your robot voice-activated tasks:

```python
agent = LLMAgent(
    model="google_genai:gemini-robotics-er-1.5-preview",
    tools=[move_forward, turn_left, turn_right],
    main_camera_usb_port="/dev/video0",  # provide usb port main camera connected to
    sounddevice_index=0,  # Your mic device
    wakeword="robot",  # The robot listens for this word in your speech
    history_len=4,
    use_memory=True, # memory system to remember important things
)
```

Then install Portaudio for audio support:
```bash
sudo apt install portaudio19-dev
```

Now just say something like **"Hey robot, bring me a beer."** — the robot listens continuously and when it hears the word "robot" anywhere in your command, it'll use the entire phrase as its new task.

### Add VLA policy as a tool

Let's make our robot to manipulate with its arms! First, you need to pretrain your own policy for it. After you have your policy, run the policy server in separate terminal.

Let's create a tool for the agent to enable it to use a VLA policy:
```python
from robocrew.robots.XLeRobot.tools import create_vla_single_arm_manipulation

grab_a_cup = create_vla_single_arm_manipulation(
    tool_name="grab_a_cup",
    tool_description="""Grab a cup in front of you and place it to the robot container""",
    server_address="localhost:8080",
    policy_name="Grigorij/act_xle_grab_a_cup",
    policy_type="act",
    arm_port=right_arm_usb,
    camera_config={"main": {"index_or_path": "/dev/video0"}, "left_arm": {"index_or_path": "/dev/video2"}},
    main_camera_object=main_camera,
    main_camera_usb_port=main_camera_usb_port,
    policy_device="cpu"
)
```

## Udev Rules Setup
To ensure your robot's components (cameras, arms, etc.) are always mapped to the same device paths, run the following script to generate udev rules:

```bash
robocrew-find-components
```

This script will guide you through connecting each component one by one and will create the necessary udev rules to maintain consistent device naming.

After running the script, you can check the generated rules at `/etc/udev/rules.d/99-robocrew.rules`, or check the symlinks:

```bash
pi@raspberrypi:~ $ ls -l /dev/arm*
lrwxrwxrwx 1 root root 7 Dec  2 11:40 /dev/arm_left -> ttyACM4
lrwxrwxrwx 1 root root 7 Dec  2 11:40 /dev/arm_right -> ttyACM2
pi@raspberrypi:~ $ ls -l /dev/cam*
lrwxrwxrwx 1 root root 6 Dec  2 11:40 /dev/camera_center -> video0
lrwxrwxrwx 1 root root 6 Dec  2 11:40 /dev/camera_right -> video2
```

## Key Parameters

- **model**: Any LangChain model
- **tools**: List of functions your robot can call (movement, manipulation)
- **main_camera_usb_port**: Your camera device (find with `ls /dev/video*`)
- **sounddevice_index**: Microphone index (optional, for voice commands)
- **wakeword**: Word that must appear in your speech to give robot a new task (default: "robot").
- **history_len**: How many conversation turns to remember (optional)
- **use_memory**: Enable memory system to remember important things (optional)
