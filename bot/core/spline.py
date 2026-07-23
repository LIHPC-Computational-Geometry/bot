from __future__ import annotations
import numpy as np

import ferrispline

from bot.core.observable import Observable

BEZIER_TYP = "bezier"
NURBS_TYP = "nurbs"

ferris = ferrispline.PyModel()


class SplineModel(Observable):
    """
    Public curve wrapper backed by ferrispline.PyModel.
    """

    def __init__(self):
        super().__init__()
        self._model = ferris
        self.curves: [str] = []
        self.scale_factor: float = 1.0

    def match_cad_scale(self, cad_model) -> None:
        """
        Automatically calculates and sets the scale factor based on the CAD model's bounding box size.
        Assumes the baseline spline size is approximately 10 units.

        Args:
            cad_model: The loaded CADModel instance containing geometric bounds.
        """
        max_size = max(cad_model.bounds.get("size", [1.0, 1.0, 1.0]))
        if max_size > 0:
            self.scale_factor = max_size / 10.0
        else:
            self.scale_factor = 1.0

    @staticmethod
    def _default_control_points(coords_a, coords_b, degree=3) -> list[list[float]]:
        points = []

        if degree == 0:
            return [coords_a]

        num_points = degree + 1
        for i in range(num_points):
            t = i / degree
            current_point = [a + (b - a) * t for a, b in zip(coords_a, coords_b)]
            points.append(current_point)

        return points

    def add_curve(
        self,
        type: str,
        degree: int,
        control_points: list[list[float]],
        weights: list[float] = None,
        knots: list[float] = None,
    ) -> str:
        """
        Adds a new curve to the model.
        Automatically scales the control points using the model's scale_factor.
        """
        scaled_cp = [
            [x * self.scale_factor, y * self.scale_factor, z * self.scale_factor]
            for x, y, z in control_points
        ]

        if type == BEZIER_TYP:
            self._notify_observers()
            tag = self._model.create_bezier(
                degree, np.array(scaled_cp, dtype=np.float64), weights
            )
            self.curves.append(tag)
            return tag
        elif type == NURBS_TYP:
            self._notify_observers()
            tag = self._model.create_nurbs(
                degree, np.array(scaled_cp, dtype=np.float64), knots, weights
            )
            self.curves.append(tag)
            return tag
        else:
            raise TypeError("Invalid curve type")

    def remove_curve(self, tag: str):
        if self._model.delete_curve(tag):
            self._notify_observers()

    def _evaluate(self, tag: str, sample: int) -> list[list[float]]:
        curve_pts = self._model.evaluate(tag, int(sample))
        return curve_pts

    def get_control_points(self, curve_tag: str) -> list[list[float]]:
        return self._model.get_control_points(curve_tag)

    def get_degree(self, tag: str) -> int:
        return self._model.get_degree(tag)

    def get_weights(self, tag: str) -> list[float]:
        return self._model.get_weights(tag)

    def get_knots(self, tag: str) -> list[float]:
        return self._model.get_knots(tag)

    def curve_kind(self, tag: str) -> str:
        return self._model.curve_kind(tag)

    def move_control_point(self, tag: str, cp_index: int, new_pt: list[float]):
        self._model.move_control_point(
            tag, cp_index, np.array(new_pt, dtype=np.float64)
        )
        self._notify_observers()

    @staticmethod
    def preview_evaluate(
        type: str,
        degree: int,
        control_points: list[list[float]],
        sample: int = 10,
        weights: list[float] = None,
        knots: list[float] = None,
    ) -> list[list[float]]:
        return ferris.preview_evaluate(
            type,
            degree,
            (np.array(control_points, dtype=np.float64), weights, knots),
            10,
        )
