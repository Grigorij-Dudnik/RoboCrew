import pytest
from unittest.mock import MagicMock
from robocrew.core.state import RobotState
from robocrew.navigation.tools import create_navigation_tools

def test_approach_mode_toggle():
    state = RobotState()
    controller = MagicMock()
    tools = create_navigation_tools(state, controller, lambda: None)
    
    # Map tools by name
    tool_map = {t.name: t for t in tools}
    
    # Enable
    tool_map['enable_approach_mode'].invoke({})
    assert state.approach_mode is True
    assert state.precision_mode is False
    
    # Disable
    tool_map['disable_approach_mode'].invoke({})
    assert state.approach_mode is False

def test_move_forward_basic():
    state = RobotState()
    state.ai_enabled = True # Must be enabled to move
    controller = MagicMock()
    tools = create_navigation_tools(state, controller, lambda: None)
    tool_map = {t.name: t for t in tools}
    
    # Run move_forward (mocked sleep ideally, but short duration fine for test)
    # We pass a very small distance to make it fast
    result = tool_map['move_forward'].invoke({"distance_meters": 0.01})
    assert "Moved forward" in result
    assert state.movement['forward'] is False # Should reset after

def test_move_forward_safety_stop():
    state = RobotState()
    state.ai_enabled = True
    controller = MagicMock()
    
    # Mock Detector to always say BLOCKED
    mock_detector = MagicMock()
    # process returns (safe_actions, overlay, metrics)
    mock_detector.process.return_value = ([], None, {})
    
    tools = create_navigation_tools(
        state, 
        controller, 
        get_frame_callback=lambda: "fake_frame",
        get_detector_callback=lambda: mock_detector
    )
    tool_map = {t.name: t for t in tools}
    
    # Should stop immediately
    result = tool_map['move_forward'].invoke({"distance_meters": 1.0})
    assert "EMERGENCY STOP" in result
