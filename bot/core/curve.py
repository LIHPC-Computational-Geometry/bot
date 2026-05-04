import nurbslib


class BezierCurve:
    """
    This class acts as a bridge between your current geometry and the Rust lib.
    """

    def __init__(self, tag: str, control_points: list[list[float]], degree: int):
        self.tag = tag
        self._engine = nurbslib.PyBezierCurve(degree, control_points, None)

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
        return self._engine.get_control_points()

    def get_degree(self):
        return self._engine.get_degree()

    def set_control_points(self, control_points: list[list[float]]):
        """Replace the internal curve engine with updated control points."""
        self._engine = nurbslib.PyBezierCurve(self.get_degree(), control_points, None)

    def get_render_data(self) -> dict:
        return {
            "tag": self.tag,
            "control_points": self.get_control_points(),
            "degree": self.get_degree(),
            "curve": self._engine.evaluate(100, False),
        }
