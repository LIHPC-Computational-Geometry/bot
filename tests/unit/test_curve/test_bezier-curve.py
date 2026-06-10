"""
Unit tests for bot.core.spline.SplineModel.

The external Rust dependency (ferrispline) is mocked to allow testing the
Python bridge and logic without requiring the compiled engine.
"""

import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from bot.core.spline import SplineModel


class _MockObserver:
    def __init__(self):
        self.calls = []

    def update(self, model):
        self.calls.append(model)


class TestSplineModelInitialization(unittest.TestCase):
    @patch("bot.core.spline.ferrispline")
    def test_empty_model_on_construction(self, mock_ferrispline):
        model = SplineModel()

        self.assertEqual(model.curves, [])
        mock_ferrispline.PyModel.assert_called_once()


class TestDefaultControlPoints(unittest.TestCase):
    def test_default_control_points_default_degree(self):
        """Tests that the method uses default degree 3 if not specified."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [30.0, 0.0, 0.0]

        # Call WITHOUT specifying the degree
        pts = SplineModel._default_control_points(coords_a, coords_b)

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
        pts = SplineModel._default_control_points(coords_a, coords_b, degree)

        # We expect 3 points: point A, middle point, and point B
        expected_pts = [[0.0, 0.0, 0.0], [5.0, 0.0, 0.0], [10.0, 0.0, 0.0]]
        self.assertEqual(pts, expected_pts)

    def test_default_control_points_count(self):
        """Tests that the number of generated points always corresponds to degree + 1."""
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [10.0, 10.0, 10.0]

        # We check for several different degrees
        for degree in [1, 3, 5, 10]:
            pts = SplineModel._default_control_points(coords_a, coords_b, degree)
            self.assertEqual(len(pts), degree + 1)

    def test_default_control_points_degree_zero(self):
        """Tests the edge case where the curve degree is 0."""
        coords_a = [1.0, 2.0, 3.0]
        coords_b = [4.0, 5.0, 6.0]

        pts = SplineModel._default_control_points(coords_a, coords_b, degree=0)

        # For degree 0, there must be only one point (point A)
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0], coords_a)


class TestAddCurve(unittest.TestCase):
    @patch("bot.core.spline.ferrispline")
    def test_add_bezier_curve(self, mock_ferrispline):
        control_points = [[0.0, 0.0, 0.0], [5.0, 5.0, 0.0], [10.0, 0.0, 0.0]]
        degree = 2

        mock_engine = MagicMock()
        mock_engine.create_bezier.return_value = "curve-1"
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        tag = model.add_curve("bezier", degree, control_points)

        self.assertEqual(tag, "curve-1")
        self.assertEqual(model.curves, ["curve-1"])
        mock_engine.create_bezier.assert_called_once()
        args, _ = mock_engine.create_bezier.call_args
        self.assertEqual(args[0], degree)
        np.testing.assert_array_equal(
            args[1], np.array(control_points, dtype=np.float64)
        )
        self.assertIsNone(args[2])

    @patch("bot.core.spline.ferrispline")
    def test_add_nurbs_curve(self, mock_ferrispline):
        control_points = [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]]
        degree = 1

        mock_engine = MagicMock()
        mock_engine.create_nurbs.return_value = "curve-nurbs"
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        tag = model.add_curve("nurbs", degree, control_points)

        self.assertEqual(tag, "curve-nurbs")
        self.assertIn("curve-nurbs", model.curves)
        mock_engine.create_nurbs.assert_called_once()

    @patch("bot.core.spline.ferrispline")
    def test_add_curve_invalid_type_raises(self, mock_ferrispline):
        mock_ferrispline.PyModel.return_value = MagicMock()
        model = SplineModel()

        with self.assertRaises(TypeError):
            model.add_curve("bspline", 2, [[0.0, 0.0, 0.0]])

    @patch("bot.core.spline.ferrispline")
    def test_add_curve_notifies_observers(self, mock_ferrispline):
        mock_engine = MagicMock()
        mock_engine.create_bezier.return_value = "curve-1"
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        observer = _MockObserver()
        model.add_observer(observer)
        model.add_curve(
            "bezier", 2, [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )

        self.assertEqual(len(observer.calls), 1)
        self.assertIs(observer.calls[0], model)


class TestCurveQueries(unittest.TestCase):
    @patch("bot.core.spline.ferrispline")
    def test_get_control_points_and_degree(self, mock_ferrispline):
        control_points = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
        mock_engine = MagicMock()
        mock_engine.create_bezier.return_value = "curve-42"
        mock_engine.get_control_points.return_value = control_points
        mock_engine.get_degree.return_value = 1
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        tag = model.add_curve("bezier", 1, control_points)

        self.assertEqual(model.get_control_points(tag), control_points)
        self.assertEqual(model.get_degree(tag), 1)
        mock_engine.get_control_points.assert_called_once_with(tag)
        mock_engine.get_degree.assert_called_once_with(tag)

    @patch("bot.core.spline.ferrispline")
    def test_evaluate_delegates_to_engine(self, mock_ferrispline):
        evaluated = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [1.0, 1.0, 1.0]]
        mock_engine = MagicMock()
        mock_engine.create_bezier.return_value = "curve-42"
        mock_engine.evaluate.return_value = evaluated
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        tag = model.add_curve("bezier", 1, [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])
        result = model._evaluate(tag, 100)

        self.assertEqual(result, evaluated)
        mock_engine.evaluate.assert_called_once_with(tag, 100)


class TestMoveControlPoint(unittest.TestCase):
    @patch("bot.core.spline.ferrispline")
    def test_move_control_point_updates_engine_and_notifies(self, mock_ferrispline):
        mock_engine = MagicMock()
        mock_engine.create_bezier.return_value = "curve-1"
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        tag = model.add_curve(
            "bezier", 2, [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]]
        )
        observer = _MockObserver()
        model.add_observer(observer)
        observer.calls.clear()

        new_pt = [5.0, 5.0, 0.0]
        model.move_control_point(tag, 1, new_pt)

        mock_engine.move_control_point.assert_called_once()
        args, _ = mock_engine.move_control_point.call_args
        self.assertEqual(args[0], tag)
        self.assertEqual(args[1], 1)
        np.testing.assert_array_equal(args[2], np.array(new_pt, dtype=np.float64))
        self.assertEqual(len(observer.calls), 1)


class TestRemoveCurve(unittest.TestCase):
    @patch("bot.core.spline.ferrispline")
    def test_remove_curve_notifies_on_success(self, mock_ferrispline):
        mock_engine = MagicMock()
        mock_engine.delete_curve.return_value = True
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        observer = _MockObserver()
        model.add_observer(observer)

        model.remove_curve("curve-1")

        mock_engine.delete_curve.assert_called_once_with("curve-1")
        self.assertEqual(len(observer.calls), 1)

    @patch("bot.core.spline.ferrispline")
    def test_remove_curve_does_not_notify_on_failure(self, mock_ferrispline):
        mock_engine = MagicMock()
        mock_engine.delete_curve.return_value = False
        mock_ferrispline.PyModel.return_value = mock_engine

        model = SplineModel()
        observer = _MockObserver()
        model.add_observer(observer)

        model.remove_curve("missing")

        self.assertEqual(len(observer.calls), 0)


if __name__ == "__main__":
    unittest.main()
