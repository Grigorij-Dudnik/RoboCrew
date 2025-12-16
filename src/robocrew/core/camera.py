import cv2
import time
from robocrew.core.state import state

def generate_frames():
    while state.running:
        if state.robot_system is None:
            time.sleep(0.1)
            continue
            
        frame = state.robot_system.get_frame()
        if frame is not None:
            try:
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            except Exception as e:
                pass
        
        time.sleep(0.01)
