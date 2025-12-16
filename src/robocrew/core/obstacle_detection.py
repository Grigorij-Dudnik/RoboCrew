import cv2
import numpy as np
import time

from robocrew.config import CAMERA_WIDTH, CAMERA_HEIGHT
from robocrew.core.state import state

class ObstacleDetector:
    def __init__(self):
        self.history = []
        self.max_history = 5
        self.last_blockage = {}
        self.latest_blockage = {'left': False, 'forward': False, 'right': False}

    def _get_chunk_average(self, frame_chunk, top_n=50):
        if frame_chunk.size == 0:
            return 0
        sorted_pixels = np.sort(frame_chunk.flatten())
        return np.mean(sorted_pixels[-top_n:])

    def process(self, frame):
        if frame is None:
            return [], frame, {}
            
        height, width = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        edges = cv2.Canny(gray, 50, 150)
        
        col_sums = np.sum(edges, axis=0)
        
        scan_height = int(height * 0.6)  
        scan_area = edges[height-scan_height:height, :]
        
        left_limit = int(width * 0.3)
        right_limit = int(width * 0.7)
        
        left_zone = scan_area[:, :left_limit]
        center_zone = scan_area[:, left_limit:right_limit]
        right_zone = scan_area[:, right_limit:]
        
        left_score = np.mean(left_zone) if left_zone.size > 0 else 0
        center_score = np.mean(center_zone) if center_zone.size > 0 else 0
        right_score = np.mean(right_zone) if right_zone.size > 0 else 0
        
        threshold = 6.0 
        
        safe_actions = ["BACKWARD"] 
        blockage = {'left': False, 'forward': False, 'right': False}
        guidance_msg = ""
        
        if center_score < threshold:
            safe_actions.append("FORWARD")
        else:
            blockage['forward'] = True
            
        if left_score < threshold:
            safe_actions.append("LEFT")
            safe_actions.append("turn_left")
        else:
            blockage['left'] = True
            
        if right_score < threshold:
            safe_actions.append("RIGHT")
            safe_actions.append("turn_right")
        else:
            blockage['right'] = True

        if "FORWARD" in safe_actions:
            safe_actions.append("move_forward")
        
        safe_actions.append("move_backward") 

        overlay = frame.copy()
        
        if blockage['forward']:
            cv2.rectangle(overlay, (left_limit, height-scan_height), (right_limit, height), (0, 0, 255), 2)
        else:
            cv2.rectangle(overlay, (left_limit, height-scan_height), (right_limit, height), (0, 255, 0), 2)
            
        if blockage['left']:
            cv2.rectangle(overlay, (0, height-scan_height), (left_limit, height), (0, 0, 255), 2)
        else:
            cv2.rectangle(overlay, (0, height-scan_height), (left_limit, height), (0, 255, 0), 2)

        if blockage['right']:
            cv2.rectangle(overlay, (right_limit, height-scan_height), (width, height), (0, 0, 255), 2)
        else:
            cv2.rectangle(overlay, (right_limit, height-scan_height), (width, height), (0, 255, 0), 2)

        if state.precision_mode:
            target_x = width // 2
            
            error = 0 
            
            cv2.line(overlay, (target_x, 0), (target_x, height), (255, 255, 0), 1)
            
            door_threshold = 15.0 
            is_door_ahead = (center_score < door_threshold)
            
            rotation_hint = None
            
            if is_door_ahead:
                guidance_msg = "PERFECT"
            else:
                guidance_msg = "ALIGNING..."
                
                if left_score < right_score:
                    guidance_msg += " (Shift Left)"
                else:
                    guidance_msg += " (Shift Right)"

        else:
            rotation_hint = None


        metrics = {
            'left': left_score,
            'center': center_score,
            'right': right_score,
            'guidance': guidance_msg,
            'rotation_hint': rotation_hint,
            'c_fwd': center_score 
        }

        self.latest_blockage = blockage
        return safe_actions, overlay, metrics
