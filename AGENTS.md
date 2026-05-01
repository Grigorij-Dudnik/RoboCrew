# AGENTS.md

## Project Memory

- Keep wrappers thin. Prefer direct use of the underlying library API unless the current use case clearly needs an abstraction.
- Do not invent safety policy, extra configuration, defensive branches, custom runtime errors, or helper classes unless the user asks for them or the surrounding framework requires them.
- Do not duplicate state that the underlying library already owns.
- Keep examples direct and minimal.
- After implementing code, do a cleanup pass and remove unnecessary variables, state, knobs, edge-case handling, and unused flexibility.
