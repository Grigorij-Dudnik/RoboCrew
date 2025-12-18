import logging
import time
import math
from typing import Any, Callable, Optional, List
from langchain_core.tools import tool
from robocrew.core.state import RobotState

logger = logging.getLogger(__name__)

# Try to import ObstacleDetector, but handle if it's not present (independent PRs)
try:
    from robocrew.vision.obstacle import ObstacleDetector
except ImportError:
    ObstacleDetector = None
    logger.warning("ObstacleDetector not found. Safety checks will be skipped or limited.")

def create_navigation_tools(
    robot_state: RobotState, 
    servo_controller: Any, 
    get_frame_callback: Callable[[], Any],
    get_detector_callback: Optional[Callable[[], Any]] = None
) -> List[Any]:
    """
    Factory to create LangChain tools for navigation.
    
    Args:
        robot_state: storage for modes and status.
        servo_controller: interface to hardware motors.
        get_frame_callback: function that returns current cv2 frame.
        get_detector_callback: function that returns the shared ObstacleDetector instance.
    """

    @tool
    def enable_approach_mode() -> str:
        """Enable Approach Mode. Use this ONLY when you need to drive very close to a surface. Disables standard safety stops."""
        robot_state.approach_mode = True
        robot_state.precision_mode = False
        return "Approach Mode ENABLED. Safety thresholds relaxed. Speed limited."

    @tool
    def disable_approach_mode() -> str:
        """Disable Approach Mode. Re-enables standard safety stops."""
        robot_state.approach_mode = False
        # Restore Speed if controller supports it
        if hasattr(servo_controller, 'set_speed'):
            servo_controller.set_speed(10000)
        return "Approach Mode DISABLED. Safety systems active."

    def _interruptible_sleep(duration: float, check_interval: float = 0.1, check_safety: bool = False, movement_type: str = None) -> bool:
        elapsed = 0
        while elapsed < duration:
            if not robot_state.ai_enabled:
                return False
                
            # Safety Check
            if check_safety and movement_type == 'FORWARD' and get_detector_callback:
                detector = get_detector_callback()
                frame = get_frame_callback()
                
                if detector and frame is not None:
                    # Pass state flags to detector
                    try:
                        safe_actions, _, _ = detector.process(
                            frame, 
                            precision_mode=robot_state.precision_mode, 
                            approach_mode=robot_state.approach_mode
                        )
                        if "FORWARD" not in safe_actions:
                            logger.info("SAFETY REFLEX: Stopping due to obstacle.")
                            return False
                    except AttributeError:
                        # Fallback if detector interface doesn't match yet
                        pass

            time.sleep(min(check_interval, duration - elapsed))
            elapsed += check_interval
        return True

    @tool
    def move_forward(distance_meters: float) -> str:
        """Drives the robot forward for a specific distance."""
        dist = float(distance_meters)
        # Simple time-based movement model
        duration = abs(dist) / 0.15 
        
        if robot_state.approach_mode:
            duration *= 2.0 # Slower
            
        logger.info(f"Moving Forward {dist}m (Duration: {duration:.1f}s)")
        
        robot_state.movement['forward'] = True
        completed = _interruptible_sleep(duration, check_safety=True, movement_type='FORWARD')
        robot_state.movement['forward'] = False
        
        if not completed:
            return "EMERGENCY STOP - Movement cancelled."
            
        return f"Moved forward {dist:.2f} meters."

    @tool
    def move_backward(distance_meters: float) -> str:
        """Drives the robot backward."""
        dist = float(distance_meters)
        duration = abs(dist) / 0.15
        
        if robot_state.approach_mode:
            duration *= 2.0
            
        robot_state.movement['backward'] = True
        completed = _interruptible_sleep(duration)
        robot_state.movement['backward'] = False
        
        if not completed:
             return "EMERGENCY STOP"
        return f"Moved backward {dist:.2f} meters."

    return [enable_approach_mode, disable_approach_mode, move_forward, move_backward]
