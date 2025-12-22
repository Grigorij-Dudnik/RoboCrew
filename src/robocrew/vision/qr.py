import cv2
import logging
from typing import Optional, Tuple, Set, Any

logger = logging.getLogger(__name__)

class QRScanner:
    """
    A vision-based QR code scanner wrapper using OpenCV.
    
    Attributes:
        seen_codes (Set[str]): A set of previously detected QR code data to prevent excessive duplicate reporting.
    """
    
    def __init__(self):
        self.detector = cv2.QRCodeDetector()
        self.seen_codes: Set[str] = set()

    def scan(self, frame: Any) -> Tuple[Optional[str], Optional[Any], Optional[str]]:
        """
        Scan a frame for QR codes.
        
        Args:
            frame: A valid OpenCV image (numpy array).
            
        Returns:
            tuple: (
                visual_data (str|None): The title or primary text for display/visuals.
                visual_points (list|None): Bounding box points of the detected QR code.
                new_context_data (str|None): The full data string if it's a NEW detection, else None.
            )
        """
        if frame is None:
            return None, None, None
            
        try:
            # detectAndDecode returns: retval (str), points (array), straight_qrcode (array)
            data, points, _ = self.detector.detectAndDecode(frame)
            
            if data and points is not None:
                # Extract a readable title (first part before a colon, if any)
                title = data.split(':', 1)[0].strip()
                
                new_context = None
                if data not in self.seen_codes:
                    self.seen_codes.add(data)
                    logger.info("QR Code detected: '%s'", data)
                    new_context = data
                
                return title, points, new_context
                    
        except Exception as e:
            logger.warning("QR Scan error: %s", e)
            
        return None, None, None

    def reset_history(self):
        """Clear the history of seen codes."""
        self.seen_codes.clear()
