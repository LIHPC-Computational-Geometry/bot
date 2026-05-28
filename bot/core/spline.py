from __future__ import annotations

import ferrispline
import numpy as np

class SplineModel():
    """
    Public curve wrapper backed by ferrispline.PyModel.

    The public methods intentionally mirror the old BezierCurve contract to keep
    existing model/viewer behavior unchanged during migration.
    """

    def __init__(self, tag: str, control_points: list[list[float]], degree: int):
        super().__init__()
        self.tag = str(tag)
        self._degree = int(degree)
        self._model = ferrispline.PyModel()
        self._curve_id: str | None = None
        self._control_points_cache: list[list[float]] = []
        self.set_control_points(control_points)

    @staticmethod
    def _default_control_points(coords_a, coords_b, degree=3):
        points = []

        if degree == 0:
            return [coords_a]

        num_points = degree + 1
        for i in range(num_points):
            t = i / degree
            current_point = [a + (b - a) * t for a, b in zip(coords_a, coords_b)]
            points.append(current_point)

        return points

    def get_tag(self):
        return self.tag

    def get_control_points(self):
        return [list(pt) for pt in self._control_points_cache]

    def get_degree(self):
        return self._degree

    def set_control_points(self, control_points: list[list[float]]):
        cp_array = np.array(control_points, dtype=np.float64)
        self._control_points_cache = cp_array.tolist()
        self._curve_id = self._model.create_bezier(self._degree, cp_array, None)

    def _evaluate(self, sample: int):
        if self._curve_id is None:
            return np.empty((0, 3), dtype=np.float64)
        curve_pts = self._model.evaluate(self._curve_id, int(sample))
        if (
            len(curve_pts.shape) == 2
            and curve_pts.shape[0] in (2, 3)
            and curve_pts.shape[1] > 3
        ):
            curve_pts = curve_pts.T
        return curve_pts

    def get_render_data(self) -> dict:
        curve_pts = self._evaluate(100)
        return {
            "tag": self.tag,
            "control_points": self.get_control_points(),
            "degree": self.get_degree(),
            "curve": curve_pts.tolist(),
        }
