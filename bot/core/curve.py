import ferrispline as ferr
import numpy as np


class BezierCurve:
    """
    This class acts as a bridge between your current geometry and the Rust lib.
    """

    def __init__(self, tag: str, control_points: list[list[float]], degree: int):
        self.tag = tag
        cp_array = np.array(control_points, dtype=np.float64)
        self._engine = ferr.PyBezierCurve(degree, cp_array, None)

    @staticmethod
    def _default_control_points(coords_a, coords_b, degree=3):
        """
        Generates the default control points for a Bezier curve.
        The points are evenly distributed along the segment connecting coords_a to coords_b.
        """
        points = []

        if degree == 0:
            return [coords_a]

        num_points = degree + 1

        for i in range(num_points):
            t = i / degree

            # Linear interpolation (lerp) for each axis (x, y, z)
            # Mathematical formula: point = A + (B - A) * t
            current_point = [a + (b - a) * t for a, b in zip(coords_a, coords_b)]

            points.append(current_point)

        return points

    def get_tag(self):
        return self.tag

    def get_control_points(self):
        cp = self._engine.get_control_points()
        if len(cp.shape) == 2 and cp.shape[0] in (2, 3) and cp.shape[1] > 3:
            cp = cp.T
        return cp.tolist()

    def get_degree(self):
        return self._engine.get_degree()

    def set_control_points(self, control_points: list[list[float]]):
        """Replace the internal curve engine with updated control points."""
        cp_array = np.array(control_points, dtype=np.float64)
        self._engine = ferr.PyBezierCurve(self.get_degree(), cp_array, None)

    def get_render_data(self) -> dict:
        curve_pts = self._engine.evaluate(100, False)
        if (
            len(curve_pts.shape) == 2
            and curve_pts.shape[0] in (2, 3)
            and curve_pts.shape[1] > 3
        ):
            curve_pts = curve_pts.T
        return {
            "tag": self.tag,
            "control_points": self.get_control_points(),
            "degree": self.get_degree(),
            "curve": curve_pts.tolist(),
        }
