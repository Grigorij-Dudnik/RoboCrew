# 🤖 RoboCrew: Copilot AI Agent Instructions

## Project Overview
RoboCrew enables rapid development of embodied LLM agents for real-world robots, focusing on vision, voice, memory, and manipulation. The architecture is modular, with clear separation between core logic, robot-specific controls, and agent orchestration.

## Key Components
- **src/robocrew/core/**: Core abstractions (LLMAgent, memory, camera, sound, tools)
- **src/robocrew/robots/XLeRobot/**: Robot-specific movement and manipulation tools (e.g., servo controls)
- **src/robocrew/scripts/**: Device setup and udev rules for consistent hardware mapping
- **examples/**: End-to-end agent setup and usage patterns

## Essential Patterns & Conventions
- **Tool Factories**: Movement/manipulation tools are created via factory functions (e.g., `create_move_forward`). These return LangChain-compatible tools for agent use.
- **Agent Construction**: See `examples/xlerobot_controler.py` for canonical agent setup. Tools are composed, then passed to `LLMAgent`.
- **Memory**: Use `remember_thing` and `recall_thing` tools for persistent memory (SQLite-backed).
- **Voice**: TTS and wakeword-activated voice commands are supported via `SoundReceiver` and the `say` tool.
- **Camera**: All vision tools expect OpenCV-compatible camera objects. Angle grid overlays are used for spatial reasoning.
- **Udev Rules**: Device paths (e.g., `/dev/arm_left`) are made stable via `robocrew-find-components` script. Always reference devices by these symlinks.

## Developer Workflows
- **Install**: `pip install robocrew` (see README for dependencies)
- **Run Example**: `python examples/xlerobot_controler.py`
- **Test**: `python -m unittest discover tests`
- **Device Setup**: `robocrew-find-components` (run as root to generate `/etc/udev/rules.d/99-robocrew.rules`)

## Integration & Extensibility
- **Add New Robot**: Implement movement/manipulation tool factories in a new robot subfolder, following the XLeRobot pattern.
- **Add New Tool**: Write a factory returning a LangChain tool, register it in the agent's tool list.
- **External Policies**: VLA manipulation tools integrate with external policy servers (see `create_vla_single_arm_manipulation`).

## Project-Specific Rules
- **Always use the angle grid overlay for navigation/alignment logic.**
- **Manipulation tools must only be called when the target is centered and close.**
- **Never hardcode device paths; use udev symlinks.**
- **Agent system prompt (see `LLMAgent.py`) encodes critical navigation/manipulation logic—do not override unless necessary.**

## References
- [README.md](../README.md): Full usage, architecture, and quickstart
- [examples/xlerobot_controler.py](../examples/xlerobot_controler.py): End-to-end agent setup
- [src/robocrew/core/LLMAgent.py](../src/robocrew/core/LLMAgent.py): Agent orchestration logic
- [src/robocrew/robots/XLeRobot/tools.py](../src/robocrew/robots/XLeRobot/tools.py): Robot tool patterns
- [src/robocrew/scripts/robocrew_find_components.py](../src/robocrew/scripts/robocrew_find_components.py): Device setup

---
For unclear or missing conventions, review the README and example scripts, or ask for clarification.