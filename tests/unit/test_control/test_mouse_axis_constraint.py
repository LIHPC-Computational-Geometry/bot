import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
try:
    from bot.control.mouse import MouseHandler

    _HAS_PANDA_DEPS = True
except ModuleNotFoundError:
    MouseHandler = None
    _HAS_PANDA_DEPS = False


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestMouseAxisConstraint(unittest.TestCase):
    def _make_handler(self, mask: int):
        handler = MouseHandler.__new__(MouseHandler)
        handler.axis_constraint_mask = mask
        return handler

    def test_mask_zero_blocks_all_axes(self):
        handler = self._make_handler(0)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(handler._apply_axis_constraint(start, candidate), start)

    def test_mask_four_keeps_only_z(self):
        handler = self._make_handler(4)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(
            handler._apply_axis_constraint(start, candidate), [1.0, 2.0, 7.0]
        )

    def test_mask_three_keeps_xy(self):
        handler = self._make_handler(3)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(
            handler._apply_axis_constraint(start, candidate), [9.0, 8.0, 3.0]
        )

    def test_mask_seven_keeps_all_axes(self):
        handler = self._make_handler(7)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(handler._apply_axis_constraint(start, candidate), candidate)


if __name__ == "__main__":
    unittest.main()
