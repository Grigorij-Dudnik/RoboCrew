import pytest
from unittest.mock import MagicMock
from robocrew.core.state import RobotState
from robocrew.navigation.precision import create_precision_tools

def test_precision_mode_toggle():
    state = RobotState()
    controller = MagicMock()
    tools = create_precision_tools(state, controller, lambda: None)
    tool_map = {t.name: t for t in tools}
    
    tool_map['enable_precision_mode'].invoke({})
    assert state.precision_mode is True
    
    tool_map['disable_precision_mode'].invoke({})
    assert state.precision_mode is False

def test_turn_execution():
    state = RobotState()
    state.ai_enabled = True
    controller = MagicMock()
    tools = create_precision_tools(state, controller, lambda: None)
    tool_map = {t.name: t for t in tools}
    
    result = tool_map['turn_right'].invoke({"angle_degrees": 90})
    assert "Turned right" in result
    
    result = tool_map['turn_left'].invoke({"angle_degrees": 45})
    assert "Turned left" in result
