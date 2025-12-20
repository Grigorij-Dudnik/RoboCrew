from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time

@dataclass
class RobotState:
    """
    Runtime state of the robot.
    Keeps track of active modes, pose, and logs.
    """
    # Modes
    ai_enabled: bool = False
    approach_mode: bool = False
    precision_mode: bool = False
    
    # Status
    current_task: str = "Idle"
    ai_status: str = "Idle"
    
    # Odometry / Pose (Estimated)
    pose: Dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "theta": 0.0})
    
    # Movement Status
    movement: Dict[str, bool] = field(default_factory=lambda: {'forward': False, 'backward': False, 'left': False, 'right': False})
    last_movement_activity: float = 0.0
    
    # Logs
    ai_logs: List[str] = field(default_factory=lambda: [])
    
    def add_ai_log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.ai_logs.append(f"[{timestamp}] {message}")
        if len(self.ai_logs) > 50:
            self.ai_logs.pop(0)

    def reset(self):
        self.ai_enabled = False
        self.approach_mode = False
        self.precision_mode = False
        self.current_task = "Idle"
        self.pose = {"x": 0.0, "y": 0.0, "theta": 0.0}
        self.movement = {'forward': False, 'backward': False, 'left': False, 'right': False}
