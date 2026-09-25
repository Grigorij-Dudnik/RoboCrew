# Agent Instructions

- Do not improve or harden code outside the specific change requested. Keep edits scoped to the task, even when nearby code looks easy to clean up.
- Do not add defensive edge-case checks or try/except blocks for cases the requested change does not require.

## Architecture

- Put cross-robot code in `src/robocrew/core/`; keep only robot-specific code under `src/robocrew/robots/<Robot>/`.
- Agent classes under `src/robocrew/robots/` are reusable skeletons. They process observations and events; they do not choose models, tools, schedules, polling intervals, or other agents.
- Tool factories live in each robot's `tools.py`. Keep tools small and independent of application orchestration.
- Each agent role has its own prompt and restricted tools. A monitor must not rely on the mission agent's prompt or tool set.
- Compose models, tools, prompts, bridges, queues, monitors, and timing in `examples/` or a deployment entrypoint.
- Deployment entrypoints may adapt paths and environment variables, but should mirror the corresponding example.
- Prefer composition over adding mode flags, callbacks, schedules, or monitor-specific branches to a reusable agent class.
- Keep event loops direct. Use the configured interval without fallback polling intervals or speculative safeguards.
