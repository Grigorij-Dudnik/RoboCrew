# 🤖 RoboCrew

**Build AI-powered robots that see, move, and manipulate objects — in a few lines of code.**

RoboCrew makes it stupidly simple to create LLM agents for physical robots. Think of it like building agents with CrewAI or AutoGen, except your agents live in the real world with cameras, microphones, wheels, and arms.

![xlerobot_schema](https://raw.githubusercontent.com/Grigorij-Dudnik/RoboCrew/master/images/main_img.png)

<div align="center">

[![PyPI version](https://badge.fury.io/py/robocrew.svg)](https://badge.fury.io/py/robocrew)
[![GitHub stars](https://img.shields.io/github/stars/Grigorij-Dudnik/RoboCrew?style=social)](https://github.com/Grigorij-Dudnik/RoboCrew)
[![Docs](https://img.shields.io/badge/docs-latest-lightblue)](https://grigorij-dudnik.github.io/RoboCrew/)
[![Discord](https://img.shields.io/static/v1?logo=discord&label=discord&message=Join&color=brightgreen)](https://discord.gg/BAe59y93)
</div>

## Features

- 🚗 **Movement** - Pre-built wheel controls for mobile robots
- 🦾 **Manipulation** - VLA models as a tools for arms control
- 👁️ **Vision** - Camera feed with automatic angle grid overlay for spatial understanding
- 🎤 **Voice** - Wake-word activated voice commands and TTS responses
- 🧠 **Intelligence** - LLM agent robot control provides complete autonomy and decision making
- 📚 **Memory** - Long-term memory to remember environment details
- 🗺️ **Navigation** *(coming soon)* - Navigation features


## Supported Robots

- **XLeRobot**
- **LeKiwi** (use XLeRobot code for it)
- More robot platforms coming soon!


## Quick Start

```bash
pip install robocrew
```

### Mobile Robot (XLeRobot)

```python
from robocrew.core.camera import RobotCamera
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_right, create_turn_left
from robocrew.robots.XLeRobot.servo_controls import ServoControler

# set up main camera
main_camera = RobotCamera("/dev/camera_center") # camera usb port Eg: /dev/video0

#set up servo controler
right_arm_wheel_usb = "/dev/arm_right"    # provide your right arm usb port. Eg: /dev/ttyACM1
servo_controler = ServoControler(right_arm_wheel_usb=right_arm_wheel_usb)

#set up tools
move_forward = create_move_forward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)

# init agent
agent = LLMAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[move_forward, turn_left, turn_right],
    main_camera=main_camera,
    servo_controler=servo_controler,
)

agent.task = "Approach a human."

agent.go()
```

### With Voice Commands

Add a microphone and a speaker to give your robot voice commands and enable it to speak back to you:

```python
agent = LLMAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[move_forward, turn_left, turn_right],
    main_camera=main_camera,
    servo_controler=servo_controler,
    sounddevice_index=2,    # provide your microphone device index.
    tts=True,               # enable text-to-speech (robot can speak).
)
```

Then install Portaudio for audio support:
```bash
sudo apt install portaudio19-dev
```

Now just say something like **"Hey robot, bring me a beer."** — the robot listens continuously and when it hears the wakeword "robot" anywhere in your command, it'll use the entire phrase as its new task.

You can find the full example at [examples/2_xlerobot_listening_and_speaking.py](examples/2_xlerobot_listening_and_speaking.py).

### Add VLA policy as a tool

Let's make our robot manipulate with its arms! First, you need to pretrain your own policy for it - [reference here](https://xlerobot.readthedocs.io/en/latest/software/getting_started/RL_VLA.html). After you have your policy, run the policy server in a separate terminal.

Let's create a tool for the agent to enable it to use a VLA policy:

```python
from robocrew.robots.XLeRobot.tools import create_vla_single_arm_manipulation

pick_up_notebook = create_vla_single_arm_manipulation(
    tool_name="Grab_a_notebook",
    tool_description="Manipulation tool to grab a notebook from the table and put it to your basket.",
    task_prompt="Grab a notebook.",
    server_address="0.0.0.0:8080",
    policy_name="Grigorij/act_right-arm-grab-notebook-2",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={"main": {"index_or_path": "/dev/camera_center"}, "right_arm": {"index_or_path": "/dev/camera_right"}},
    main_camera_object=main_camera,
    policy_device="cpu",
)
```

You can find the full example at [examples/3_xlerobot_arm_manipulation.py](examples/3_xlerobot_arm_manipulation.py).


## Give to USB ports a constant names (Udev rules)

To ensure your robot's components (cameras, arms, etc.) are always mapped to the same device paths, run the following script to generate udev rules:

```bash
robocrew-setup-usb-modules
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


# 🤖 RoboCrew 

**Build AI-powered robots that see, move, and manipulate objects — in a few lines of code.**

RoboCrew makes it stupidly simple to create LLM agents for physical robots. Think of it like building agents with CrewAI or AutoGen, except your agents live in the real world with cameras, microphones, wheels, and arms.

![xlerobot_schema](https://raw.githubusercontent.com/Grigorij-Dudnik/RoboCrew/master/images/main_img.png)

<div align="center">

[![PyPI version](https://badge.fury.io/py/robocrew.svg)](https://badge.fury.io/py/robocrew)
[![GitHub stars](https://img.shields.io/github/stars/Grigorij-Dudnik/RoboCrew?style=social)](https://github.com/Grigorij-Dudnik/RoboCrew)
[![Docs](https://img.shields.io/badge/docs-latest-lightblue)](https://grigorij-dudnik.github.io/RoboCrew/)
[![Discord](https://img.shields.io/static/v1?logo=discord&label=discord&message=Join&color=brightgreen)](https://discord.gg/BAe59y93)
</div>

---

## ✨ Features

- 🚗 **Movement** - Pre-built wheel controls for mobile robots
- 🦾 **Manipulation** - VLA models as tools for arms control
- 👁️ **Vision** - Camera feed with automatic angle grid overlay for spatial understanding
- 🎤 **Voice** - Wake-word activated voice commands and TTS responses
- 🧠 **Intelligence** - LLM agent control provides complete autonomy and decision making
- 📚 **Memory** - Long-term memory to remember environment details
- 🗺️ **Navigation** *(coming soon)* - Autonomous navigation features

---

## 🎯 How It Works

![How It Works Diagram](https://raw.githubusercontent.com/Grigorij-Dudnik/RoboCrew/master/images/robot_agent.png)

**The RoboCrew Intelligence Loop:**

1. 👂 **Input** - Voice commands, text tasks, or autonomous operation
2. 🧠 **LLM Processing** - Gemini analyzes the task and environment
3. 🛠️ **Tool Selection** - AI chooses appropriate tools (move, turn, grab the apple, etc.)
4. 🤖 **Robot Actions** - Wheels and arms execute commands
5. 📹 **Visual Feedback** - Cameras capture results with augmented overlay
6. 🔄 **Adaptive Loop** - LLM evaluates results and adjusts strategy

This closed-loop system creates AI agents that perceive → reason → act, but in the physical world!

---

## 🎨 Supported Robots

- ✅ **XLeRobot** - Full support for all features
- ✅ **LeKiwi** - Use XLeRobot code (compatible platform)
- 🔜 More robot platforms coming soon! [Request your platform →](https://github.com/Grigorij-Dudnik/RoboCrew/issues)

---

## 🚀 Quick Start

```bash
pip install robocrew
```

### 📱 Mobile Robot (XLeRobot)

```python
from robocrew.core.camera import RobotCamera
from robocrew.core.LLMAgent import LLMAgent
from robocrew.robots.XLeRobot.tools import create_move_forward, create_turn_right, create_turn_left
from robocrew.robots.XLeRobot.servo_controls import ServoControler

# 📷 Set up main camera
main_camera = RobotCamera("/dev/camera_center")  # camera usb port Eg: /dev/video0

# 🎛️ Set up servo controller
right_arm_wheel_usb = "/dev/arm_right"  # provide your right arm usb port. Eg: /dev/ttyACM1
servo_controler = ServoControler(right_arm_wheel_usb=right_arm_wheel_usb)

# 🛠️ Set up tools
move_forward = create_move_forward(servo_controler)
turn_left = create_turn_left(servo_controler)
turn_right = create_turn_right(servo_controler)

# 🤖 Initialize agent
agent = LLMAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[move_forward, turn_left, turn_right],
    main_camera=main_camera,
    servo_controler=servo_controler,
)

# 🎯 Give it a task and go!
agent.task = "Approach a human."
agent.go()
```

---

### 🎤 With Voice Commands

Add a microphone and speaker to give your robot voice commands and enable it to speak back to you:

```python
agent = LLMAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[move_forward, turn_left, turn_right],
    main_camera=main_camera,
    servo_controler=servo_controler,
    sounddevice_index=2,  # 🎙️ provide your microphone device index
    tts=True,  # 🔊 enable text-to-speech (robot can speak)
)
```

Then install Portaudio for audio support:

```bash
sudo apt install portaudio19-dev
```

Now just say something like **"Hey robot, bring me a beer."** — the robot listens continuously and when it hears the wakeword "robot" anywhere in your command, it'll use the entire phrase as its new task.

📖 **Full example:** [examples/2_xlerobot_listening_and_speaking.py](examples/2_xlerobot_listening_and_speaking.py)

---

### 🦾 Add VLA Policy as a Tool

Let's make our robot manipulate with its arms! 

First, you need to pretrain your own policy for it - [reference here](https://xlerobot.readthedocs.io/en/latest/software/getting_started/RL_VLA.html).

After you have your policy, run the policy server in a separate terminal. Let's create a tool for the agent to enable it to use a VLA policy:

```python
from robocrew.robots.XLeRobot.tools import create_vla_single_arm_manipulation

# 🎯 Create a specialized manipulation tool
pick_up_notebook = create_vla_single_arm_manipulation(
    tool_name="Grab_a_notebook",
    tool_description="Manipulation tool to grab a notebook from the table and put it to your basket.",
    task_prompt="Grab a notebook.",
    server_address="0.0.0.0:8080",
    policy_name="Grigorij/act_right-arm-grab-notebook-2",
    policy_type="act",
    arm_port=right_arm_wheel_usb,
    servo_controler=servo_controler,
    camera_config={
        "main": {"index_or_path": "/dev/camera_center"},
        "right_arm": {"index_or_path": "/dev/camera_right"}
    },
    main_camera_object=main_camera,
    policy_device="cpu",
)
```

📖 **Full example:** [examples/3_xlerobot_arm_manipulation.py](examples/3_xlerobot_arm_manipulation.py)

---

## 🔧 Give USB Ports Constant Names (Udev Rules)

To ensure your robot's components (cameras, arms, etc.) are always mapped to the same device paths, run the following script to generate udev rules:

```bash
robocrew-setup-usb-modules
```

This script will guide you through connecting each component one by one and will create the necessary udev rules to maintain consistent device naming.

**After running the script**, you can check the generated rules at `/etc/udev/rules.d/99-robocrew.rules`, or check the symlinks:

```bash
pi@raspberrypi:~ $ ls -l /dev/arm*
lrwxrwxrwx 1 root root 7 Dec 2 11:40 /dev/arm_left -> ttyACM4
lrwxrwxrwx 1 root root 7 Dec 2 11:40 /dev/arm_right -> ttyACM2

pi@raspberrypi:~ $ ls -l /dev/cam*
lrwxrwxrwx 1 root root 6 Dec 2 11:40 /dev/camera_center -> video0
lrwxrwxrwx 1 root root 6 Dec 2 11:40 /dev/camera_right -> video2
```

---

## 📚 Documentation

For detailed documentation, tutorials, and API references, visit our [official documentation](https://grigorij-dudnik.github.io/RoboCrew/).

---

## 💬 Community & Support

- 💭 [Join our Discord](https://discord.gg/BAe59y93) - Get help, share projects, discuss features
- 📖 [Read the Docs](https://grigorij-dudnik.github.io/RoboCrew/) - Comprehensive guides and API reference
- 🐛 [Report Issues](https://github.com/Grigorij-Dudnik/RoboCrew/issues) - Found a bug? Let us know!
- ⭐ [Star on GitHub](https://github.com/Grigorij-Dudnik/RoboCrew) - Show your support!

---

## 🙏 Acknowledgments

Built with ❤️ for the robotics and AI community. Special thanks to all contributors and early adopters!