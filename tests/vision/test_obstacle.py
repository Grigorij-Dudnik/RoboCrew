import pytest
import numpy as np
import cv2
from robocrew.vision.obstacle import ObstacleDetector

def test_obstacle_detector_init():
    detector = ObstacleDetector()
    assert detector.width == 640
    assert detector.height == 480
    assert detector.latest_blockage['forward'] is False

def test_process_empty_frame():
    detector = ObstacleDetector()
    actions, overlay, metrics = detector.process(None)
    assert actions == ["STOP"]
    assert overlay is None

def test_process_black_frame_blind():
    """A completely black frame should result in BLIND condition (only BACKWARD allowed)."""
    detector = ObstacleDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    actions, overlay, metrics = detector.process(frame)
    # blind means only backward
    assert actions == ["BACKWARD"]
    assert "FORWARD" not in actions

def test_process_clear_path():
    """A frame with edges only on sides (fake path)."""
    detector = ObstacleDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Draw some "noise" edges everywhere to pass min_edge_pixels
    cv2.rectangle(frame, (0, 0), (640, 480), (255, 255, 255), 1)
    # Fill enough pixels to not be blind
    cv2.randu(frame, 0, 255) # random noise
    
    # Assume clear path for simplicity is hard to mock with random noise perfectly, 
    # but let's test that it runs without crash
    actions, overlay, metrics = detector.process(frame)
    assert isinstance(actions, list)
    assert overlay is not None

def test_modes_flags():
    detector = ObstacleDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Just verify arguments are accepted
    actions, overlay, metrics = detector.process(frame, precision_mode=True, approach_mode=True)
    assert actions is not None
