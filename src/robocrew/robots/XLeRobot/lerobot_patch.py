import logging
from functools import wraps

def apply_silent_calibration_patch():
    """
    Monkey-patches LeRobot's robot classes so they silently load 
    existing calibration files without blocking the thread with an input() prompt.
    """
    
    # 1. Patch SOFollower (used by SO-100)
    try:
        from lerobot.robots.so_follower.so_follower import SOFollower
        original_so_calibrate = SOFollower.calibrate
        
        @wraps(original_so_calibrate)
        def patched_so_calibrate(self, *args, **kwargs):
            if self.calibration:
                logging.info(f"[RoboCrew] Silently loading calibration for SOFollower '{self.id}'")
                self.bus.write_calibration(self.calibration)
                return
            # If no calibration exists at all, fallback to the original method
            return original_so_calibrate(self, *args, **kwargs)
            
        SOFollower.calibrate = patched_so_calibrate
    except ImportError:
        pass  # Skip if the class isn't installed/available

    # 2. Patch KochFollower (if you ever use Alexander Koch's robot)
    try:
        from lerobot.robots.koch_follower.koch_follower import KochFollower
        original_koch_calibrate = KochFollower.calibrate
        
        @wraps(original_koch_calibrate)
        def patched_koch_calibrate(self, *args, **kwargs):
            if self.calibration:
                logging.info(f"[RoboCrew] Silently loading calibration for KochFollower '{self.id}'")
                self.bus.write_calibration(self.calibration)
                return
            return original_koch_calibrate(self, *args, **kwargs)
            
        KochFollower.calibrate = patched_koch_calibrate
    except ImportError:
        pass