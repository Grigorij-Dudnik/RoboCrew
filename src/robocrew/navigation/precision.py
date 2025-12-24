import logging
import time
from typing import Any, Callable, Optional, List
from langchain_core.tools import tool
from robocrew.core.state import RobotState

logger = logging.getLogger(__name__)

# Independent PR: Try import obstacle detector, optional
try:
    from robocrew.vision.obstacle import ObstacleDetector
except ImportError:
    logger.warning("ObstacleDetector not found. Precision visuals will not be computed.")

def create_precision_tools(
    robot_state: RobotState,
    servo_controller: Any,
    get_frame_callback: Callable[[], Any],
    get_detector_callback: Optional[Callable[[], Any]] = None
) -> List[Any]:
    
    @tool
    def enable_precision_mode() -> str:
        """Enable Precision Mode to see alignment targets for narrow gaps/doors."""
        robot_state.precision_mode = True
        return "Precision Mode ENABLED. Visual alignment targets active."
        
    @tool
    def disable_precision_mode() -> str:
        """Disable Precision Mode."""
        robot_state.precision_mode = False
        return "Precision Mode DISABLED."
        
    def _interruptible_turn(duration: float) -> bool:
        start = time.time()
        while time.time() - start < duration:
            if not robot_state.ai_enabled: 
                return False
            time.sleep(0.05)
        return True

    @tool
    def turn_right(angle_degrees: float) -> str:
        """Turns the robot right by angle in degrees."""
        angle = float(angle_degrees)
        duration = max(abs(angle) / 60, 0.15)
        
        logger.info(f"Turning Right {angle} deg ({duration:.2f}s)")
        robot_state.movement['right'] = True
        completed = _interruptible_turn(duration)
        robot_state.movement['right'] = False
        
        if not completed: return "EMERGENCY STOP"
        return f"Turned right by {angle} degrees."

    @tool
    def turn_left(angle_degrees: float) -> str:
        """Turns the robot left by angle in degrees."""
        angle = float(angle_degrees)
        duration = max(abs(angle) / 60, 0.15)
        
        logger.info(f"Turning Left {angle} deg ({duration:.2f}s)")
        robot_state.movement['left'] = True
        completed = _interruptible_turn(duration)
        robot_state.movement['left'] = False
        
        if not completed: return "EMERGENCY STOP"
        return f"Turned left by {angle} degrees."

    return [enable_precision_mode, disable_precision_mode, turn_right, turn_left]
