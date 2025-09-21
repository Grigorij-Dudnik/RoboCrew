# Wheel Controls Tutorial

This guide shows how to steer wheels using `wheel_controls.py` with the existing SDK and config.

## Prerequisites

- Python 3.x
- Dependencies from `requirements.txt` installed (pyserial, customtkinter if using GUIs)
- Your servos connected to a serial adapter (e.g. `/dev/ttyUSB0`)
- A wheel section in `dual_mapper_config.json` (used by the dual mapper app)

Example wheel config snippet (from `dual_mapper_config.json` under `portB.wheel`):

```json
{
  "speed": 1000,
  "wheels": [
    { "id": 7, "role": "both", "calibration": {"Up": 1, "Down": -1, "Left": -1, "Right": 1} },
    { "id": 8, "role": "steer", "calibration": {"Up": 0, "Down": 0, "Left": -1, "Right": 1} },
    { "id": 9, "role": "both", "calibration": {"Up": -1, "Down": 1, "Left": -1, "Right": 1} }
  ]
}
```

- `speed`: base speed magnitude applied to each wheel
- `wheels[n].role`: which actions affect the wheel
  - `drive` and `both` respond to Forward/Backward
  - `steer` and `both` respond to Left/Right
- `wheels[n].calibration`: direction per action; multiply by speed
  - Use -1 for reverse, 0 to ignore, 1 for forward

## Quick start

1. Connect to the serial port

```python
from wheel_controls import connect_serial
sdk = connect_serial("/dev/ttyUSB0")
```

2. Load the wheel config

```python
import json
cfg = json.load(open("dual_mapper_config.json"))
wheel_cfg = cfg["portB"]["wheel"]
```

3. Put wheels into wheel mode (one time)

```python
from wheel_controls import apply_wheel_modes
apply_wheel_modes(sdk, wheel_cfg)
```

4. Move

```python
from wheel_controls import go_forward, go_backward, turn_left, turn_right, stop_wheels

# Forward / Backward
mp = go_forward(sdk, wheel_cfg)   # returns {wheel_id: speed}
mp = go_backward(sdk, wheel_cfg)

# Turning
mp = turn_left(sdk, wheel_cfg)
mp = turn_right(sdk, wheel_cfg)

# Stop all wheels
mp = stop_wheels(sdk, wheel_cfg)
```

## Behavior details

- Movement functions compute a per-wheel speed using: `calibration[action] * speed`
- Role filtering:
  - Forward/Backward affect wheels with role `drive` or `both`
  - Left/Right affect wheels with role `steer` or `both`
- Each call writes speeds via `sdk.sync_write_wheel_speeds` and returns the map

## Tips

- If wheels do not move in the desired direction, flip the calibration sign for that action.
- You can adjust the base `speed` value in the config for stronger/weaker motion.
- Ensure you set the correct `port` path for your hardware.

## Safety

- Keep the robot lifted during first tests.
- Use `stop_wheels` to halt motion quickly.
- Verify `apply_wheel_modes` is called; position mode won’t respond to wheel speed commands.

## Troubleshooting

- Permission denied opening serial: add your user to `dialout` or run with appropriate permissions.
- No motion: confirm IDs, wiring, power, and that wheel mode was applied.
- Inverted turn: swap `Left`/`Right` signs in calibration for the affected wheel(s).

## Optional: tiny script example

Create `demo_drive.py` in `feetech_gui/`:

```python
import json
from wheel_controls import connect_serial, apply_wheel_modes, go_forward, go_backward, turn_left, turn_right, stop_wheels
import time

sdk = connect_serial("/dev/ttyUSB0")
wheel_cfg = json.load(open("dual_mapper_config.json"))["portB"]["wheel"]
apply_wheel_modes(sdk, wheel_cfg)

print("Forward 1s...")
go_forward(sdk, wheel_cfg)
time.sleep(1)

print("Stop")
stop_wheels(sdk, wheel_cfg)

print("Left 0.5s...")
turn_left(sdk, wheel_cfg)
time.sleep(0.5)

print("Stop")
stop_wheels(sdk, wheel_cfg)
```

Run it from this folder after connecting your hardware.
