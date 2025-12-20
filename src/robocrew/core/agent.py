import logging
import time
from typing import Any, List, Optional, Dict
from robocrew.core.state import RobotState

logger = logging.getLogger(__name__)

# Conditional Imports for Independence
try:
    from robocrew.vision.qr import QRScanner
except ImportError:
    QRScanner = None

try:
    from robocrew.vision.obstacle import ObstacleDetector
except ImportError:
    ObstacleDetector = None

class NavigationAgent:
    """
    High-level agent that coordinates vision, tools, and decision making.
    """
    def __init__(self, robot_state: RobotState, system_prompt: str = None):
        self.state = robot_state
        self.system_prompt = system_prompt or "You are a robot assistant."
        
        # Initialize Subsystems
        self.qr_scanner = QRScanner() if QRScanner else None
        self.detector = ObstacleDetector() if ObstacleDetector else None
        
        # Memory / History
        self.message_history: List[Any] = []
        
    def step(self, frame: Any) -> str:
        """
        Execute one step of the agent loop:
        1. Process Vision (QR, Obstacle)
        2. Update State
        3. Decision (Placeholder for LLM)
        """
        if frame is None:
            return "No Frame"
            
        # 1. Vision
        scan_result = None
        if self.qr_scanner:
            scan_result = self.qr_scanner.scan(frame)
            if scan_result[2]: # New context
                logger.info(f"Context Update: {scan_result[2]}")
                self.state.add_ai_log(f"Saw QR: {scan_result[0]}")
        
        safe_actions = ["STOP"]
        if self.detector:
            # Pass state flags to detector
            safe_actions, overlay, metrics = self.detector.process(
                frame, 
                precision_mode=self.state.precision_mode,
                approach_mode=self.state.approach_mode
            )
        
        # 2. Update Overlay (if we had a display component, we'd send it there)
        # For now, just log
        if self.state.ai_enabled:
             return f"Safe Actions: {safe_actions}"
        else:
             return "Paused"
             
    def run_loop(self, get_frame_cb, max_steps=10):
        """Simple run loop for testing."""
        self.state.ai_enabled = True
        for i in range(max_steps):
            frame = get_frame_cb()
            status = self.step(frame)
            logger.info(f"Step {i}: {status}")
            time.sleep(0.1)
