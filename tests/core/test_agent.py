import pytest
import numpy as np
from unittest.mock import MagicMock, patch
import sys

# Mock missing modules to ensure tests pass in this isolated branch
# We must do this BEFORE importing agent
# But wait, python caches imports. Safe way is patch.dict(sys.modules) around the import
# However, pytest collects tests by importing the file.
# So we need the file to be importable.
# The `agent.py` uses try-import, so it IS importable even without them.
# We just need to Mock them in the TEST function if we want to verify interaction.

from robocrew.core.state import RobotState
from robocrew.core.agent import NavigationAgent

def test_agent_init():
    state = RobotState()
    agent = NavigationAgent(state)
    assert agent.state == state
    # QR/Detector might be None if imports failed, which is expected behavior in this branch
    # So we don't assert they are not None unless we mock sys.modules to simulate presence.

def test_agent_step_no_vision():
    """Test step execution when vision modules are missing (fallback)."""
    state = RobotState()
    agent = NavigationAgent(state)
    
    # Force them to None just in case they were found
    agent.qr_scanner = None
    agent.detector = None
    
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    result = agent.step(frame)
    # If not enabled, it says Paused?
    # Default ai_enabled=False
    assert result == "Paused"
    
    agent.state.ai_enabled = True
    result = agent.step(frame)
    # With no detector, safe_actions defaults to ["STOP"] in current impl?
    # In agent.py: safe_actions = ["STOP"].
    # If self.detector: update it.
    assert result == "Safe Actions: ['STOP']"

def test_agent_step_with_mock_vision():
    """Test interaction with vision modules if they exist."""
    state = RobotState()
    agent = NavigationAgent(state)
    agent.state.ai_enabled = True
    
    # Inject Mocks
    mock_qr = MagicMock()
    mock_qr.scan.return_value = ("Title", None, "NewContext")
    agent.qr_scanner = mock_qr
    
    mock_detector = MagicMock()
    # returns (safe, overlay, metrics)
    mock_detector.process.return_value = (["FORWARD"], None, {})
    agent.detector = mock_detector
    
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    result = agent.step(frame)
    
    assert "FORWARD" in result
    assert "Saw QR: Title" in agent.state.ai_logs[0]
