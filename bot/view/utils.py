"""View-layer utility helpers (colour generation, etc.)."""

import colorsys


class ColorGenerator:
    """Utility class for generating visually distinct colours."""

    @staticmethod
    def generate_distinct_colors(n: int) -> list[tuple[float, float, float]]:
        """
        Generate *n* visually distinct RGB colours using evenly-spaced HSV hues.

        Args:
            n: Number of colours to generate.

        Returns:
            List of ``(r, g, b)`` tuples with values in ``[0, 1]``.
        """
        return [colorsys.hsv_to_rgb(i / n, 0.65, 1.0) for i in range(n)]
