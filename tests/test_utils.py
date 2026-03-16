import os
import sys
import math
import unittest
from unittest.mock import MagicMock
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

from robocrew.core.utils import (
    calculate_angle_marks,
    basic_augmentation,
    draw_precision_mode_aug,
    stop_listening_during_tool_execution,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_image(width=640, height=480):
    """Return a black BGR image as a numpy array."""
    return np.zeros((height, width, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# calculate_angle_marks — pure math, no cv2
# ---------------------------------------------------------------------------

class TestCalculateAngleMarks(unittest.TestCase):

    def test_center_mark_at_center_pixel_and_zero_angle(self):
        """With center_angle=0, the middle mark must be at pixel width//2 with angle 0."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        mid = len(marks) // 2
        x, angle = marks[mid]
        self.assertEqual(angle, 0, "Middle mark angle should be 0")
        self.assertAlmostEqual(x, 320, delta=1, msg="Middle mark x should be ~320")

    def test_correct_number_of_marks_for_fov(self):
        """FOV=120 with 10-degree spacing gives 13 marks (-60..60)."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        self.assertEqual(len(marks), 13)

    def test_correct_number_of_marks_for_narrow_fov(self):
        """FOV=60 with 10-degree spacing gives 7 marks (-30..30)."""
        marks = calculate_angle_marks(width=640, h_fov=60, center_angle=0)
        self.assertEqual(len(marks), 7)

    def test_angle_coverage_matches_fov(self):
        """First and last angles should span the full FOV symmetrically."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        angles = [a for _, a in marks]
        self.assertEqual(angles[0], -60)
        self.assertEqual(angles[-1], 60)

    def test_angles_are_multiples_of_mark_step(self):
        """Every angle must be a multiple of the 10-degree step."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        for _, angle in marks:
            self.assertEqual(angle % 10, 0, f"Angle {angle} is not a multiple of 10")

    def test_uniform_pixel_spacing(self):
        """Pixel spacing between consecutive marks must be uniform (±1 px rounding)."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        xs = [x for x, _ in marks]
        spacings = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        expected = spacings[0]
        for s in spacings:
            self.assertAlmostEqual(s, expected, delta=1,
                                   msg=f"Non-uniform spacing: {s} vs {expected}")

    def test_marks_are_symmetric_around_center(self):
        """Angles left of center must mirror angles right of center."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        n = len(marks)
        for i in range(n // 2):
            left_angle = marks[i][1]
            right_angle = marks[n - 1 - i][1]
            self.assertEqual(left_angle, -right_angle,
                             f"Asymmetric: {left_angle} vs {right_angle}")

    def test_center_angle_shifts_grid(self):
        """With center_angle=30, angle 30 should land near pixel 320."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=30)
        mark_at_30 = next((x for x, a in marks if a == 30), None)
        self.assertIsNotNone(mark_at_30, "No mark with angle=30 found")
        self.assertAlmostEqual(mark_at_30, 320, delta=2,
                               msg="Angle 30 should be at center pixel with center_angle=30")

    def test_pixels_increase_left_to_right(self):
        """Pixel positions must be strictly increasing (left to right)."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        xs = [x for x, _ in marks]
        for i in range(len(xs) - 1):
            self.assertGreater(xs[i + 1], xs[i],
                               f"Pixels not increasing at index {i}: {xs[i]} >= {xs[i+1]}")

    def test_angle_to_pixel_mapping_is_linear(self):
        """Each angle step of 10 degrees should map to the same pixel delta."""
        marks = calculate_angle_marks(width=640, h_fov=120, center_angle=0)
        pixels_per_degree = 640 / 120  # ~5.33
        for x, angle in marks:
            expected_x = 320 + angle * pixels_per_degree
            self.assertAlmostEqual(x, expected_x, delta=1,
                                   msg=f"Angle {angle}: x={x}, expected~{expected_x:.0f}")


# ---------------------------------------------------------------------------
# basic_augmentation — pixel smoke tests (cv2 draws on real array)
# ---------------------------------------------------------------------------

class TestBasicAugmentation(unittest.TestCase):

    def test_returns_ndarray(self):
        result = basic_augmentation(make_image())
        self.assertIsInstance(result, np.ndarray)

    def test_shape_unchanged(self):
        img = make_image(640, 480)
        result = basic_augmentation(img)
        self.assertEqual(result.shape, (480, 640, 3))

    def test_yellow_baseline_drawn_at_y25(self):
        """Horizontal baseline at y=25 must be yellow (BGR 0,255,255)."""
        img = make_image()
        result = basic_augmentation(img)
        # Sample mid-image x so we avoid any edge artefacts
        pixel = result[25, 200]
        self.assertEqual(list(pixel), [0, 255, 255], "Baseline at y=25 should be yellow")

    def test_orange_tick_marks_drawn(self):
        """There must be orange pixels within the tick mark band (y=15..35)."""
        img = make_image()
        result = basic_augmentation(img)
        orange = np.array([0, 100, 255], dtype=np.uint8)
        # Slice the tick-mark band
        band = result[15:36, :, :]
        mask = np.all(band == orange, axis=2)
        self.assertTrue(mask.any(), "No orange tick marks found in y=15..35 band")

    def test_center_tick_is_at_center_x(self):
        """With default params, orange tick at y=20 should appear at x≈320."""
        img = make_image()
        result = basic_augmentation(img)
        orange = np.array([0, 100, 255], dtype=np.uint8)
        row = result[20, :, :]
        orange_xs = [x for x in range(row.shape[0]) if np.array_equal(row[x], orange)]
        self.assertTrue(len(orange_xs) > 0, "No orange pixels at y=20")
        # Find tick centers (deduplicate neighbouring pixels from 2px line width)
        centers = []
        for x in orange_xs:
            if not centers or x - centers[-1] > 5:
                centers.append(x)
        mid_center = centers[len(centers) // 2]
        self.assertAlmostEqual(mid_center, 320, delta=3,
                               msg=f"Center tick at x={mid_center}, expected ~320")

    def test_precision_mode_draws_green_pixels(self):
        """Precision mode must add green arm-range lines (BGR 0,255,0)."""
        img = make_image()
        result = basic_augmentation(img, navigation_mode="precision")
        green = np.array([0, 255, 0], dtype=np.uint8)
        mask = np.all(result == green, axis=2)
        self.assertTrue(mask.any(), "No green pixels found in precision mode")

    def test_normal_mode_has_no_green_pixels(self):
        """Normal mode must NOT draw green arm-range lines."""
        img = make_image()
        result = basic_augmentation(img, navigation_mode="normal")
        green = np.array([0, 255, 0], dtype=np.uint8)
        mask = np.all(result == green, axis=2)
        self.assertFalse(mask.any(), "Green pixels found in normal mode — unexpected")


# ---------------------------------------------------------------------------
# stop_listening_during_tool_execution decorator
# ---------------------------------------------------------------------------

class TestStopListeningDecorator(unittest.TestCase):

    def test_stop_and_start_called_around_function(self):
        """stop_listening must be called before and start_listening after the function."""
        receiver = MagicMock()
        call_order = []
        receiver.stop_listening.side_effect = lambda: call_order.append("stop")
        receiver.start_listening.side_effect = lambda: call_order.append("start")

        @stop_listening_during_tool_execution(receiver)
        def my_func():
            call_order.append("func")

        my_func()
        self.assertEqual(call_order, ["stop", "func", "start"])

    def test_none_receiver_does_not_crash(self):
        """Passing None as receiver must not raise any exception."""
        @stop_listening_during_tool_execution(None)
        def my_func():
            return 42
        self.assertEqual(my_func(), 42)

    def test_preserves_return_value(self):
        receiver = MagicMock()
        @stop_listening_during_tool_execution(receiver)
        def add(x, y):
            return x + y
        self.assertEqual(add(3, 4), 7)

    def test_preserves_kwargs(self):
        receiver = MagicMock()
        @stop_listening_during_tool_execution(receiver)
        def greet(name="world"):
            return f"Hello {name}"
        self.assertEqual(greet(name="Robot"), "Hello Robot")

    def test_stop_called_exactly_once(self):
        receiver = MagicMock()
        @stop_listening_during_tool_execution(receiver)
        def my_func(): pass
        my_func()
        receiver.stop_listening.assert_called_once()
        receiver.start_listening.assert_called_once()

    def test_functools_wraps_preserves_name(self):
        """Decorated function must keep its original __name__."""
        @stop_listening_during_tool_execution(None)
        def my_special_function():
            pass
        self.assertEqual(my_special_function.__name__, "my_special_function")


if __name__ == "__main__":
    unittest.main()
