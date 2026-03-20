from .core.lerobot_patch import apply_silent_calibration_patch

# Apply the LeRobot patches globally the moment 'robocrew' is imported
apply_silent_calibration_patch()