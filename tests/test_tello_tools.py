import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from robocrew.robots.Tello import tools as tello_tools


class FakeTello:
    def __init__(self, speed=20):
        self.commands = []
        self.is_flying = True
        self.move_up_calls = []
        self.move_down_calls = []

    def send_rc_control(self, left_right_velocity, forward_backward_velocity, up_down_velocity, yaw_velocity):
        self.commands.append((left_right_velocity, forward_backward_velocity, up_down_velocity, yaw_velocity))

    def set_speed(self, _speed):
        return None

    def move_up(self, centimeters):
        self.move_up_calls.append(centimeters)

    def move_down(self, centimeters):
        self.move_down_calls.append(centimeters)


class TestTelloRcMove(unittest.TestCase):
    def test_rc_move_sends_hover_after_normal_movement(self):
        tello = FakeTello()

        with patch("robocrew.robots.Tello.tools.time.sleep"):
            result = tello_tools._rc_move(tello, 30, (0, 30, 0, 0))

        self.assertTrue(result)
        self.assertEqual(tello.commands[0], (0, 30, 0, 0))
        self.assertEqual(tello.commands[-1], (0, 0, 0, 0))

    def test_rc_move_does_not_claim_movement_when_landed(self):
        tello = FakeTello()
        tello.is_flying = False

        result = tello_tools._rc_move(tello, 20, (0, 20, 0, 0))

        self.assertFalse(result)
        self.assertEqual(tello.commands, [])


class TestTelloMovementTools(unittest.TestCase):
    def _assert_tool_mapping(self, factory, expected_rc):
        tello = FakeTello()

        with patch("robocrew.robots.Tello.tools._rc_move", return_value=True) as rc_move:
            tool = factory(tello)
            result = tool.invoke({"centimeters": 30})

        self.assertIn("30", result)
        rc_move.assert_called_once_with(tello, 30, expected_rc)

    def test_move_forward_mapping(self):
        self._assert_tool_mapping(tello_tools.create_move_forward, (0, 30, 0, 0))

    def test_move_backward_mapping(self):
        self._assert_tool_mapping(tello_tools.create_move_backward, (0, -30, 0, 0))

    def test_strafe_right_mapping(self):
        self._assert_tool_mapping(tello_tools.create_strafe_right, (30, 0, 0, 0))

    def test_strafe_left_mapping(self):
        self._assert_tool_mapping(tello_tools.create_strafe_left, (-30, 0, 0, 0))

    def test_move_up_uses_tello_move_tool(self):
        tello = FakeTello()
        tool = tello_tools.create_move_up(tello)

        result = tool.invoke({"centimeters": 30})

        self.assertIn("30", result)
        self.assertEqual(tello.move_up_calls, [30])

    def test_move_down_uses_tello_move_tool(self):
        tello = FakeTello()
        tool = tello_tools.create_move_down(tello)

        result = tool.invoke({"centimeters": 30})

        self.assertIn("30", result)
        self.assertEqual(tello.move_down_calls, [30])


if __name__ == "__main__":
    unittest.main()
