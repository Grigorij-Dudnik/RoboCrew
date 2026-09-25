# Agent Instructions

- Do not improve or harden code outside the specific change requested. Keep edits scoped to the task, even when nearby code looks easy to clean up.
- Do not add defensive edge-case checks or try/except blocks for cases the requested change does not require.

## Architecture

- Put cross-robot code in `src/robocrew/core/`; keep only robot-specific code under `src/robocrew/robots/<Robot>/`.
- Extract shared code only when multiple robots already use it; do not design for hypothetical reuse.
- Keep refactors direct and minimal; avoid one-use wrappers, helpers, and caches, and check the final diff for unnecessary growth.
- Examples and deployment entrypoints configure models, tools, prompts, and external dependencies, then pass them into agents.
- Robot agents may own robot-specific runtime loops and dynamic tool visibility when these are part of that robot's execution model.
- Tool factories live in each robot's `tools.py`. Keep tools small and independent of application orchestration.
- Each agent role has its own prompt and restricted tools. A monitor must not rely on the mission agent's prompt or tool set.
- Deployment entrypoints may adapt paths and environment variables, but should mirror the corresponding example.
- Prefer composition over generic mode flags, callbacks, or monitor-specific branches.
- Keep event loops direct. Use the configured interval without fallback polling intervals or speculative safeguards.
