import threading
import time
import cv2
import logging
from typing import Optional, Dict, Any

from robocrew.core.state import state
from robocrew.robots.XLeRobot.servo_controls import ServoControler
from robocrew.config import WHEEL_USB, HEAD_USB, CAMERA_PORT, CAMERA_WIDTH, CAMERA_HEIGHT, CAMERA_BUFFER_SIZE

logger = logging.getLogger(__name__)

class RobotSystem:
    def __init__(self):
        self.controller: Optional[ServoControler] = None
        self.camera = None
        self.camera_lock = threading.Lock()
        self.running = True
        
        self._init_camera()
        self._init_servos()
        
        state.robot_system = self
        
    def _init_camera(self):
        try:
            self.camera = cv2.VideoCapture(CAMERA_PORT)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, CAMERA_BUFFER_SIZE)
            if not self.camera.isOpened():
                logger.error(f"Failed to open camera on {CAMERA_PORT}")
                self.camera = None
            else:
                logger.info(f"Camera initialized on {CAMERA_PORT}")
            state.camera = self.camera
        except Exception as e:
            logger.error(f"Camera init error: {e}")
            self.camera = None
            state.camera = None

    def _init_servos(self):
        logger.info(f"Connecting servos ({WHEEL_USB}, {HEAD_USB})...")
        try:
            self.controller = ServoControler(
                WHEEL_USB, 
                HEAD_USB,
                enable_arm=True
            )
            state.controller = self.controller
            
            if self.controller.arm_enabled:
                state.arm_connected = True
                try:
                    pos = self.controller.get_arm_position()
                    state.update_arm_positions(pos)
                except Exception as e:
                    logger.warning(f"Could not read arm: {e}")
            
            try:
                pos = self.controller.get_head_position()
                state.head_yaw = round(pos.get(7, 0), 1)
                state.head_pitch = round(pos.get(8, 0), 1)
            except Exception as e:
                logger.warning(f"Could not read head: {e}")
                
            logger.info("Servos connected successfully")
        except Exception as e:
            logger.error(f"Servo connection failed: {e}")
            state.last_error = str(e)
            self.controller = None

    def get_frame(self):
        if not self.camera:
            return None
        with self.camera_lock:
            ret, frame = self.camera.read()
            if ret:
                return frame
            return None

    def cleanup(self):
        self.running = False
        if self.controller:
            try:
                self.controller.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting servos: {e}")
        
        if self.camera:
            self.camera.release()
            
    def emergency_stop(self):
        if self.controller:
            self.controller._wheels_stop()
