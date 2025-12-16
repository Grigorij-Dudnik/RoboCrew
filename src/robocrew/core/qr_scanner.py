import cv2
import numpy as np

class QRScanner:
    def __init__(self):
        self.detector = cv2.QRCodeDetector()
        self.seen_codes = set()
        
    def scan(self, frame, pose=None):
        if frame is None:
            return None, None, None
            
        try:
            data, points, _ = self.detector.detectAndDecode(frame)
            
            if data:
                if data not in self.seen_codes:
                    self.seen_codes.add(data)
                    return data, points, data
                return data, points, None
                
        except Exception:
            pass
            
        return None, None, None
