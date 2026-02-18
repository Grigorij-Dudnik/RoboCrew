---
title: VLA Manipulation Tutorial
description: How to use Vision-Language-Action (VLA) policies as tools in RoboCrew.
---

RoboCrew allows your robot to perform complex physical tasks—like grabbing objects—by utilizing Vision-Language-Action (VLA) policies as tools. These tools bridge the gap between high-level LLM reasoning and low-level motor control.

## 1. Prerequisites

Before the agent can use an arm, you must have a VLA server running in a separate terminal. RoboCrew uses the **LeRobot** framework for this:

```bash
# Run the VLA server (example for ACT policy)
python -m lerobot.async_inference.policy_server --host=0.0.0.0 --port=8080

```

## 2. Creating a VLA Tool

You define a manipulation tool using the `create_vla_single_arm_manipulation` factory function. This binds a specific pretrained policy to a tool the AI agent can call.

### Example Configuration

```python
from robocrew.robots.XLeRobot.tools import create_vla_single_arm_manipulation

pick_up_notebook = create_vla_single_arm_manipulation(
    tool_name="Grab_a_notebook",
    tool_description="Use this tool when you are very close to a notebook and looking straight at it.",
    task_prompt="Grab a notebook.",
    server_address="0.0.0.0:8080",
    policy_name="Grigorij/act_right-arm-grab-notebook-2", # Path to pretrained policy
    policy_type="act",
    arm_port="/dev/arm_right",
    servo_controler=servo_controler,
    camera_config={
        "main": {"index_or_path": "/dev/camera_center"},
        "right_arm": {"index_or_path": "/dev/camera_right"}
    },
    main_camera_object=main_camera,
    execution_time=45  # Seconds to run the policy
)

```

## 3. Critical Manipulation Rules

For successful manipulation, the agent must follow these hardware-specific constraints defined in the system prompt:

* **Arm Reach**: The robot's arm reach is very short (~30cm).
* **Mode Requirement**: Always switch to **PRECISION** mode before attempting any manipulation to tilt the camera down.
* **The Green Line**: In PRECISION mode, augmented "green lines" appear in the camera feed. The **BASE** of the target object must be **BELOW** this line before the tool is activated.
* **Alignment**: The target must be centered in the view. If it is off-center, the agent should use `strafe` or `turn` tools to align first.

## 4. Execution Workflow

1. **Release Camera**: When a VLA tool is activated, it temporarily "steals" the camera from the LLM agent so the policy can process the video feed directly.
2. **Control Loop**: The tool connects to the `RobotClient`, sends the `task_prompt` to the server, and executes actions for the specified `execution_time`.
3. **Restore State**: After completion, the tool re-opens the camera for the agent and resets the robot's head to the normal position.
4. **Verification**: The agent is instructed to always verify the success of the manipulation via the camera feed after the tool finishes.