---
title: Audio and Voice Tutorial
description: How to use audio and voice features in the RoboCrew project.
---

RoboCrew allows your robot to listen for voice commands using wake-word detection and respond verbally using Text-to-Speech (TTS). This creates a hands-free "Intelligence Loop" where the robot perceives, reasons, and acts based on your spoken instructions.

## 1. Enabling Voice in the Agent

To utilize audio features, you must provide a microphone device index and enable the TTS flag during the initialization of the `LLMAgent` or `XLeRobotAgent`.

### Basic Configuration

```python
agent = XLeRobotAgent(
    model="google_genai:gemini-3-flash-preview",
    tools=[...],
    sounddevice_index=2,  # 🎙️ Provide your microphone device index
    wakeword="Bob",       # 🗣️ Custom wake-word (default is "robot")
    tts=True,             # 🔊 Enable Text-to-Speech
    # ... other params
)

```

## 2. Audio Hardware Setup

Before running the code, ensure your system has the necessary audio libraries installed for handling microphone input:

```bash
sudo apt install portaudio19-dev
pip install pyaudio audioop-lts

```

## 3. How Listening Works

The audio system runs through a `SoundReceiver` class that manages background recording and transcription:

* **Continuous Listening**: The robot monitors the environment for a specific volume threshold (RMS).
* **Wake-word Detection**: It records audio segments and transcribes them. If the defined `wakeword` is detected in the transcription, the entire phrase is set as the agent's new active task.
* **Task Updates**: While the robot is idle or performing a task, it continuously checks the `task_queue` for new verbal instructions.

## 4. How Speaking Works

When `tts=True` is set, the agent is granted access to a specialized `say` tool:

* **Communication**: The LLM can proactively use the `say` tool to greet users, provide status updates (e.g., "I have found the blue notebook"), or ask for clarification.
* **Echo Prevention**: To prevent the robot from hearing and transcribing its own voice, the `SoundReceiver` automatically pauses listening while the `say` tool is speaking and resumes once finished.

## 5. Voice Operation Sequence

1. **Idle Mode**: The robot waits and listens.
2. **Command**: You say, *"Hey **robot**, bring me a beer"*.
3. **Activation**: The `SoundReceiver` identifies the wake-word "robot" and updates `agent.task` to "bring me a beer".
4. **Feedback**: The agent may use the `say` tool to respond: *"Okay, looking for a beer now"*.
5. **Execution**: The agent enters its main loop to identify and retrieve the object.