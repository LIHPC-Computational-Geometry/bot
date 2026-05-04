import unittest
from bot.view.utils import ColorGenerator


class TestColorGenerator(unittest.TestCase):
    def test_returns_correct_number_of_colors(self):
        for n in [1, 3, 10]:
            colors = ColorGenerator.generate_distinct_colors(n)
            self.assertEqual(len(colors), n)

    def test_colors_are_rgb_tuples_in_unit_range(self):
        colors = ColorGenerator.generate_distinct_colors(5)
        for r, g, b in colors:
            self.assertGreaterEqual(r, 0.0)
            self.assertLessEqual(r, 1.0)
            self.assertGreaterEqual(g, 0.0)
            self.assertLessEqual(g, 1.0)
            self.assertGreaterEqual(b, 0.0)
            self.assertLessEqual(b, 1.0)

    def test_colors_are_distinct(self):
        colors = ColorGenerator.generate_distinct_colors(6)
        # All colors must be unique
        self.assertEqual(len(set(colors)), len(colors))

    def test_single_color(self):
        colors = ColorGenerator.generate_distinct_colors(1)
        self.assertEqual(len(colors), 1)
        r, g, b = colors[0]
        self.assertIsInstance(r, float)

    def test_empty(self):
        colors = ColorGenerator.generate_distinct_colors(0)
        self.assertEqual(colors, [])


if __name__ == "__main__":
    unittest.main()
