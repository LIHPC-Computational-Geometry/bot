import nurbslib

class BezierCurve:
    """
    Cette classe agit comme un pont entre ta géométrie actuelle et la lib Rust.
    """
    def __init__(self, tag: str, control_points: list[list[float]], degree: int):
        self.tag = tag
        self._engine = nurbslib.PyBezierCurve(degree, control_points, None)

    @staticmethod
    def _default_control_points(coords_a, coords_b, degree=3):
        """
        Génère les points de contrôle par défaut pour une courbe de Bézier.
        Les points sont répartis uniformément le long du segment reliant coords_a à coords_b.
        """
        points = []

        if degree == 0:
            return [coords_a]

        num_points = degree + 1

        for i in range(num_points):
            t = i / degree

            # Interpolation linéaire (lerp) pour chaque axe (x, y, z)
            # Formule mathématique : point = A + (B - A) * t
            current_point = [
                a + (b - a) * t
                for a, b in zip(coords_a, coords_b)
            ]

            points.append(current_point)

        return points

    def get_tag(self):
        return self.tag

    def get_control_points(self):
        return self._engine.get_control_points()

    def get_degree(self):
        return self._engine.get_degree()

    def get_render_data(self) -> dict:
        return {
            'tag': self.tag,
            'control_points': self.get_control_points(),
            'degree': self.get_degree(),
            'curve': self._engine.evaluate(100, False)
        }