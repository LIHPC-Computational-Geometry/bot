"""
Unit tests for bot.core.curve.BezierCurve.

The external Rust dependency (ferrispline) is mocked to allow testing the
Python bridge and logic without requiring the compiled engine.
"""

import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from bot.core.curve import BezierCurve


class TestBezierCurve(unittest.TestCase):
    @patch("bot.core.rust_block.ferrispline")
    def test_initialization_and_attributes(self, mock_nurbslib):
        """Tests the initialization of the curve and access to its basic attributes."""
        # 1. Data preparation
        tag = "curve_1"
        control_points = [[0.0, 0.0, 0.0], [5.0, 5.0, 0.0], [10.0, 0.0, 0.0]]
        degree = 2

        # 2. Mock configuration to simulate the ferrispline engine
        mock_model_instance = MagicMock()
        mock_model_instance.create_bezier.return_value = "curve-1"
        mock_model_instance.evaluate.return_value = np.array(control_points)
        mock_nurbslib.PyModel.return_value = mock_model_instance

        # 3. Object creation
        curve = BezierCurve(tag, control_points, degree)

        # 4. Verifications (Assertions)
        self.assertEqual(curve.get_tag(), "curve_1")
        self.assertEqual(curve.get_control_points(), control_points)
        self.assertEqual(curve.get_degree(), degree)

        # Ensure the Rust model was called with the correct arguments
        mock_nurbslib.PyModel.assert_called_once()
        args, kwargs = mock_model_instance.create_bezier.call_args
        self.assertEqual(args[0], degree)
        np.testing.assert_array_equal(args[1], np.array(control_points))
        self.assertIsNone(args[2])

    def test_default_control_points_default_degree(self):
        """Tests that the method uses default degree 3 if not specified."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [30.0, 0.0, 0.0]

        # Call WITHOUT specifying the degree
        pts = BezierCurve._default_control_points(coords_a, coords_b)

        # Since the default degree is 3, we expect 3 + 1 = 4 points
        expected_pts = [
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [20.0, 0.0, 0.0],
            [30.0, 0.0, 0.0],
        ]
        self.assertEqual(len(pts), 4)
        self.assertEqual(pts, expected_pts)

    def test_default_control_points_distribution(self):
        """Tests the uniform spatial distribution of the default generated points."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [10.0, 0.0, 0.0]
        degree = 2

        # Execute static method
        pts = BezierCurve._default_control_points(coords_a, coords_b, degree)

        # We expect 3 points: point A, middle point, and point B
        expected_pts = [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [10.0, 0.0, 0.0]]
        self.assertEqual(pts, expected_pts)

    def test_default_control_points_count(self):
        """Tests that the number of generated points always corresponds to degree + 1."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [10.0, 10.0, 10.0]

        # We check for several different degrees
        for degree in [1, 3, 5, 10]:
            pts = BezierCurve._default_control_points(coords_a, coords_b, degree)
            self.assertEqual(len(pts), degree + 1)

    def test_default_control_points_degree_zero(self):
        """Tests the edge case where the curve degree is 0."""
        coords_a = [1.0, 2.0, 3.0]
        coords_b = [4.0, 5.0, 6.0]

        pts = BezierCurve._default_control_points(coords_a, coords_b, degree=0)

        # For degree 0, there must be only one point (point A)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0], coords_a)

    @patch("bot.core.rust_block.ferrispline")
    def test_get_render_data(self, mock_nurbslib):
        """Tests the structure and content of the render dictionary (used by the viewer)."""
        tag = "42"
        control_points = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
        degree = 1

        # Simulated result of curve evaluation by the engine
        mock_curve_eval = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [1.0, 1.0, 1.0]]

        # Mock configuration
        mock_model_instance = MagicMock()
        mock_model_instance.create_bezier.return_value = "curve-42"
        mock_model_instance.evaluate.return_value = np.array(mock_curve_eval)
        mock_nurbslib.PyModel.return_value = mock_model_instance

        # Object creation and data retrieval
        curve = BezierCurve(tag, control_points, degree)
        data = curve.get_render_data()

        # Verification of the presence of all required keys
        self.assertIn("tag", data)
        self.assertIn("control_points", data)
        self.assertIn("degree", data)
        self.assertIn("curve", data)

        # Verifications of values
        self.assertEqual(data["tag"], "42")
        self.assertEqual(data["control_points"], control_points)
        self.assertEqual(data["degree"], degree)
        self.assertEqual(data["curve"], mock_curve_eval)

        # Ensure the engine was called to generate 100 points
        mock_model_instance.evaluate.assert_called_once_with("curve-42", 100)


if __name__ == "__main__":
    unittest.main()
