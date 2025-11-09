# XLeRobot Control

Minimal documentation for controlling the XLeRobot.

## High-Level Control (`robot_controls.py`)

Use the `XLeRobotControler` class for basic movement and head control.

### Initialization

```python
from robocrew.robots.XLeRobot.robot_controls import XLeRobotControler

# Adjust serial ports as needed
robot = XLeRobotControler(
    wheel_arm_usb="/dev/ttyUSB0",
    head_arm_usb="/dev/ttyUSB1"
)

# IMPORTANT for first use: Set wheels to the correct mode
robot.apply_wheel_modes()
```

### Movement

- `go_forward(meters: float)`
- `go_backward(meters: float)`
- `turn_left(degrees: float)`
- `turn_right(degrees: float)`

### Head Control

- `turn_head_yaw(degrees: float)`
- `turn_head_pitch(degrees: float)`

## Low-Level SDK (`sdk.py`)

The `ScsServoSDK` class provides direct serial communication with SCS servos for fine-grained control. It is the foundation for `wheel_controls.py`.

### Key Methods

- `list_ports() -> List[str]`: Lists available serial ports.
- `connect(port: str, baudrate: int) -> bool`: Connects to a servo bus.
- `disconnect()`: Closes the serial connection.

### Servo Control

- `set_wheel_mode(servo_id: int)`: Sets a servo to continuous rotation (wheel) mode.
- `sync_write_wheel_speeds(servo_speeds: Dict[int, int])`: Synchronously sets speeds for multiple wheels. `speed` is from -10000 to 10000.
- `sync_write_positions(servo_positions: Dict[int, int])`: Synchronously sets goal positions for multiple servos in joint mode.
- `sync_read_positions(servo_ids: List[int]) -> Dict[int, int]`: Reads the current positions of multiple servos.
