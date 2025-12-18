import pytest
import numpy as np
import cv2
from unittest.mock import MagicMock, patch
from robocrew.vision.qr import QRScanner

def test_qr_scanner_initialization():
    scanner = QRScanner()
    assert scanner.seen_codes == set()
    assert scanner.detector is not None

def test_scan_no_frame():
    scanner = QRScanner()
    title, points, new_context = scanner.scan(None)
    assert title is None
    assert points is None
    assert new_context is None

@patch('cv2.QRCodeDetector')
def test_scan_detection_new_code(mock_detector_cls):
    # Setup mock
    mock_detector = mock_detector_cls.return_value
    # Mock detectAndDecode to return valid data
    # (data, points, straight_qrcode)
    mock_points = np.array([[[0,0], [10,0], [10,10], [0,10]]])
    mock_detector.detectAndDecode.return_value = ("Room:Kitchen", mock_points, None)
    
    scanner = QRScanner()
    # Replace the real detector with our mock (constructor is already called, so we patch the instance attr)
    scanner.detector = mock_detector
    
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    title, points, new_context = scanner.scan(frame)
    
    assert title == "Room"
    assert new_context == "Room:Kitchen"
    np.testing.assert_array_equal(points, mock_points)
    assert "Room:Kitchen" in scanner.seen_codes

@patch('cv2.QRCodeDetector')
def test_scan_detection_duplicate_code(mock_detector_cls):
    mock_detector = mock_detector_cls.return_value
    mock_points = np.array([[[0,0], [10,0], [10,10], [0,10]]])
    mock_detector.detectAndDecode.return_value = ("Room:Kitchen", mock_points, None)
    
    scanner = QRScanner()
    scanner.detector = mock_detector
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # First scan
    scanner.scan(frame)
    
    # Second scan (same code)
    title, points, new_context = scanner.scan(frame)
    
    assert title == "Room"
    assert new_context is None # Should be None as it's not new
    np.testing.assert_array_equal(points, mock_points)

def test_reset_history():
    scanner = QRScanner()
    scanner.seen_codes.add("test")
    scanner.reset_history()
    assert len(scanner.seen_codes) == 0
