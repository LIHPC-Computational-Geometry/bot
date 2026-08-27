"""Unit tests for curve geometry serialization."""

import unittest

from bot.viewer.serialize import (
    bytes_to_scalar_list,
    curve_delta_to_curve_info,
    pack_curve_delta,
    scalar_count_from_bytes,
    scalars_to_bytes,
)


class TestScalarSerialization(unittest.TestCase):
    def test_scalars_round_trip(self):
        values = [1.0, 1.0, 1.0, 1.0]
        buf = scalars_to_bytes(values)
        self.assertEqual(scalar_count_from_bytes(buf), 4)
        self.assertEqual(bytes_to_scalar_list(buf, 4), values)

    def test_pack_bezier_with_four_weights(self):
        curve_pts = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        control_pts = [
            [0.0, 0.0, 0.0],
            [1.0, 3.0, 0.0],
            [4.0, 3.0, 0.0],
            [5.0, 0.0, 0.0],
        ]
        weights = [1.0, 1.0, 1.0, 1.0]

        delta = pack_curve_delta(
            curve_pts,
            edges=[(0, 1)],
            curve_type="bezier",
            control_points=control_pts,
            degree=3,
            weights=weights,
        )

        self.assertEqual(delta["weight_count"], 4)
        info = curve_delta_to_curve_info("spline:curve-test", delta)
        self.assertEqual(info["weights"], weights)
        self.assertEqual(info["control_points"], control_pts)

    def test_pack_nurbs_with_knots_and_weights(self):
        curve_pts = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        control_pts = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        knots = [0.0, 0.0, 0.0, 0.0, 0.5, 1.0, 1.0, 1.0, 1.0]
        weights = [1.0, 2.0]

        delta = pack_curve_delta(
            curve_pts,
            edges=[(0, 1)],
            curve_type="nurbs",
            control_points=control_pts,
            degree=3,
            knots=knots,
            weights=weights,
        )

        self.assertEqual(delta["knot_count"], len(knots))
        self.assertEqual(delta["weight_count"], len(weights))
        info = curve_delta_to_curve_info("spline:curve-test", delta)
        self.assertEqual(info["knots"], knots)
        self.assertEqual(info["weights"], weights)


if __name__ == "__main__":
    unittest.main()
