![Logo](https://raw.githubusercontent.com/Grigorij-Dudnik/RoboCrew-assets/master/Logo/logo_writing.png)

RoboCrew makes it stupidly simple to create LLM agents for physical robots. Think of it like building agents with CrewAI or AutoGen, except your agents live in the real world with cameras, microphones, wheels, and arms.


<p align="center">
  <img src="https://raw.githubusercontent.com/Grigorij-Dudnik/RoboCrew-assets/master/Demo_videos/robocrew_v3_9fps.gif" alt="RoboCrew demo" width="700">
</p>
<p align="center"><em>RoboCrew agent cleaning up a table.</em></p>

<p align="center">
  <a href="https://github.com/Grigorij-Dudnik/RoboCrew/stargazers"><img src="https://img.shields.io/github/stars/Grigorij-Dudnik/RoboCrew?style=for-the-badge&color=gold&label=⭐️ Stars" alt="Stars"></a>
  <a href="https://pypi.org/project/robocrew/"><img src="https://img.shields.io/pypi/dm/robocrew?style=for-the-badge&color=green" alt="Downloads"></a>
  <a href="https://discord.gg/BAe59y93"><img src="https://img.shields.io/badge/Discord-Join%20Us-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://grigorij-dudnik.github.io/RoboCrew/"><img src="https://img.shields.io/badge/Docs-Read-orange?style=for-the-badge" alt="Docs"></a>
  <a href="https://pypi.org/project/robocrew/"><img src="https://img.shields.io/pypi/v/robocrew?style=for-the-badge&color=blue" alt="PyPI version"></a>
</p>




---

## ✨ Features

- 🚗 **Movement** - Pre-built wheel controls for mobile robots
- 🦾 **Manipulation** - VLA models as tools for arms control
- 👁️ **Vision** - Camera feed with automatic angle grid overlay for spatial understanding
- 🎤 **Voice** - Wake-word activated voice commands and TTS responses
- 🗺️ **LiDAR** - Top-down mapping with LiDAR sensor
- 🧠 **Intelligence** - LLM agent control provides complete autonomy and decision making
- 📚 **Memory** - Long-term memory to remember environment details

## 🚀 Quick Start

```bash
pip install robocrew
```
To run GUI use:
```bash
robocrew-gui
```
![images/main2.jpg](https://raw.githubusercontent.com/Grigorij-Dudnik/RoboCrew/feature/readme_improvement/images/main2.jpg)

## 🎯 How It Works

<div align="center">

<img src="https://github.com/Grigorij-Dudnik/RoboCrew/blob/573b6ff33e961676ad349b694b8c20b4cb8cd9ac/images/robot_agent.png" alt="How It Works Diagram" width="500">
</div>


**The RoboCrew Intelligence Loop:**

1. 👂 **Input** - Voice commands, text tasks, or autonomous operation
2. 🧠 **LLM Processing** - Gemini analyzes the task and environment
3. 🛠️ **Tool Selection** - AI chooses appropriate tools (move, turn, grab the apple, etc.)
4. 🤖 **Robot Actions** - Wheels and arms execute commands
5. 📹 **Visual Feedback** - Cameras capture results with augmented overlay
6. 🔄 **Adaptive Loop** - LLM evaluates results and adjusts strategy

This closed-loop system creates AI agents that perceive → reason → act, but in the physical world!


## 🎨 Supported Robots

- ✅ **XLeRobot** - Full support for all features
- 🥝 **LeKiwi** - Use XLeRobot code (compatible platform)
- 🚙 **Earth Rover mini plus** - Full support
- 🔜 More robot platforms coming soon! [Request your platform →](https://github.com/Grigorij-Dudnik/RoboCrew/issues)


## 📱 Scripts to Use:

To gain full control over RoboCrew features, you can create your own script. Simplest example:

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

### 🎤 Enable Listening and Speaking

📖 **Docs:**  https://grigorij-dudnik.github.io/RoboCrew-docs/guides/examples/audio/

💻 **Code example:** [examples/2_xlerobot_listening_and_speaking.py](examples/2_xlerobot_listening_and_speaking.py)

---

### 🦾 Add VLA Policy as a Tool

Let's make our robot manipulate with its arms! 

📖 **Docs:** https://grigorij-dudnik.github.io/RoboCrew-docs/guides/examples/vla-as-tools/

💻 **Code example:** [examples/3_xlerobot_arm_manipulation.py](examples/3_xlerobot_arm_manipulation.py)

---

### 🧠 Increase intelligence with multiagent communication:

📖 **Docs:** https://grigorij-dudnik.github.io/RoboCrew-docs/guides/examples/multiagent/

💻 **Code example:** [examples/4_xlerobot_multiagent_cooperation.py](examples/4_xlerobot_multiagent_cooperation.py)


## 💬 Community & Support

- 💭 [Join our Discord](https://discord.gg/BAe59y93) - Get help, share projects, discuss features
- 📖 [Read the Docs](https://grigorij-dudnik.github.io/RoboCrew/) - Comprehensive guides and API reference
- 🐛 [Report Issues](https://github.com/Grigorij-Dudnik/RoboCrew/issues) - Found a bug? Let us know!
- ⭐ [Star on GitHub](https://github.com/Grigorij-Dudnik/RoboCrew) - Show your support!


## 🙏 Acknowledgments


Built with ❤️ for the robotics and AI community. Special thanks to all contributors and early adopters!
