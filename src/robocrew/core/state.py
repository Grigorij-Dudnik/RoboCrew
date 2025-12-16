import threading
import time
from typing import Dict, Any, Optional

class RobotState:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.running = True
        self.controller = None
        self.camera = None
        self.agent = None
        self.robot_system = None
        self.arm_connected = False
        
        self.ai_enabled = False
        self.ai_status = "Idle"
        self.ai_logs = []
        
        self.movement = {
            'forward': False,
            'backward': False,
            'left': False,
            'right': False
        }
        
        self.head_yaw = 0.0
        self.head_pitch = 0.0
        
        self.arm_positions = {}
        self.gripper_closed = False
        
        self.last_remote_activity = 0
        self.last_movement_activity = 0
        
        self.last_error = ""
        
        self.pose = {'x': 0, 'y': 0, 'theta': 0}
        
        self.precision_mode = False

    def update_movement(self, data: Dict[str, Any]):
        self.movement.update({
            'forward': bool(data.get('forward', False)),
            'backward': bool(data.get('backward', False)),
            'left': bool(data.get('left', False)),
            'right': bool(data.get('right', False))
        })
    
    def get_movement(self) -> Dict[str, bool]:
        return self.movement.copy()
    
    def stop_all_movement(self):
        self.movement = {k: False for k in self.movement}
        if self.controller:
            self.controller._wheels_stop()

    def add_ai_log(self, message: str):
        timestamp = time.strftime("%H:%M:%S")
        self.ai_logs.append(f"[{timestamp}] {message}")
        if len(self.ai_logs) > 50:
            self.ai_logs.pop(0)
            
        self.ai_status = message

    def update_arm_positions(self, positions: Dict[int, float]):
        self.arm_positions.update(positions)

    def get_arm_positions(self) -> Dict[str, float]:
        from robocrew.core.arm import arm_controller
        return {
            'shoulder_pan': self.arm_positions.get(1, 0),
            'shoulder_lift': self.arm_positions.get(2, 0),
            'elbow_flex': self.arm_positions.get(3, 0),
            'wrist_flex': self.arm_positions.get(4, 0),
            'wrist_roll': self.arm_positions.get(5, 0),
            'gripper': self.arm_positions.get(6, 0)
        }

    def set_control_mode(self, mode: str) -> bool:
        if mode == 'drive':
            self.ai_enabled = False
            return True
        elif mode == 'ai':
            if self.agent:
                self.ai_enabled = True
                return True
        return False

    def get_control_mode(self) -> str:
        if self.ai_enabled:
            return 'ai'
        return 'drive'

    def get_detector(self):
        if not hasattr(self, '_detector') or self._detector is None:
             from robocrew.core.obstacle_detection import ObstacleDetector
             self._detector = ObstacleDetector()
        return self._detector

state = RobotState()
