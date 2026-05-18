import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from bot.control.picker import RayPicker
    from panda3d.core import Point2

    _HAS_PANDA_DEPS = True
except ModuleNotFoundError:
    RayPicker = None
    _HAS_PANDA_DEPS = False


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestRayPicker(unittest.TestCase):
    def setUp(self):
        self.base = MagicMock()
        if _HAS_PANDA_DEPS:
            from panda3d.core import NodePath
            # Simulate attachNewNode by wrapping the CollisionNode in a real NodePath
            self.base.camera.attachNewNode.side_effect = lambda node: NodePath(node)

        self.picker = RayPicker(self.base)

    def test_init_sets_masks_and_colliders(self):
        self.base.camera.attachNewNode.assert_called_once()
        self.assertEqual(self.picker.traverser.getNumColliders(), 1)
        # Check mask is MASK_CURVE (2) | MASK_CP (4) = 6 in binary context (or 3 if bit(0) and bit(1))
        # BitMask32.bit(1) = 2, bit(2) = 4, so 2 | 4 = 6
        self.assertEqual(self.picker.picker_node.getFromCollideMask().getWord(), 6)
        self.assertEqual(self.picker.picker_node.getIntoCollideMask().getWord(), 0)

    def _make_mock_entry(self, tags: dict, depth: float = 10.0):
        """Helper to create a mock collision entry."""
        entry = MagicMock()
        np = MagicMock()
        entry.getIntoNodePath.return_value = np
        np.hasNetTag.side_effect = lambda t: t in tags
        np.getNetTag.side_effect = lambda t: tags.get(t)

        surface_pt = MagicMock()
        surface_pt.getY.return_value = depth
        entry.getSurfacePoint.return_value = surface_pt
        return entry

    def test_pick_entry_no_collision(self):
        self.picker.queue = MagicMock()
        self.picker.queue.getNumEntries.return_value = 0
        self.picker.traverser = MagicMock()
        self.picker.picker_ray = MagicMock()

        result = self.picker.pick_entry(Point2(0, 0), "cp")
        self.assertIsNone(result)
        self.picker.traverser.traverse.assert_called_once_with(self.base.render)

    def test_pick_entry_wrong_kind(self):
        entry = self._make_mock_entry({"pick_kind": "curve"})

        self.picker.queue = MagicMock()
        self.picker.queue.getNumEntries.return_value = 1
        self.picker.queue.getEntry.return_value = entry
        self.picker.traverser = MagicMock()
        self.picker.picker_ray = MagicMock()

        result = self.picker.pick_entry(Point2(0, 0), "cp")
        self.assertIsNone(result)

    def test_pick_entry_success_with_priority_sorting(self):
        entry_curve = self._make_mock_entry({"pick_kind": "curve"})
        entry_cp = self._make_mock_entry({"pick_kind": "cp"})

        self.picker.queue = MagicMock()
        self.picker.queue.getNumEntries.return_value = 2
        self.picker.queue.getEntry.side_effect = [entry_curve, entry_cp]
        self.picker.traverser = MagicMock()
        self.picker.picker_ray = MagicMock()

        # Mock the sorting priority function.
        # CP should get higher priority (0) than curve (1).
        self.picker._get_priority_distance_depth = MagicMock(
            side_effect=[
                (1, 0.0, 10.0),  # Priority for Curve
                (0, 0.0, 5.0),   # Priority for CP
            ]
        )

        result = self.picker.pick_entry(Point2(0, 0), "cp")
        self.assertEqual(result, entry_cp)

    def test_get_metadata_curve(self):
        entry = self._make_mock_entry({"pick_kind": "curve", "curve_tag": "tag1"})
        entry.getSurfacePoint.return_value = "surface_point"

        meta = self.picker.get_metadata(entry)
        self.assertEqual(meta["pick_kind"], "curve")
        self.assertEqual(meta["curve_tag"], "tag1")
        self.assertIsNone(meta["cp_index"])
        self.assertEqual(meta["point"], "surface_point")

    def test_get_metadata_cp_with_center(self):
        entry = self._make_mock_entry({"pick_kind": "cp", "curve_tag": "tag2", "cp_index": "5"})
        solid = MagicMock()
        solid.getCenter.return_value = "center_point"
        entry.getInto.return_value = solid

        self.base.render.getRelativePoint.return_value = "relative_center"

        meta = self.picker.get_metadata(entry)
        self.assertEqual(meta["pick_kind"], "cp")
        self.assertEqual(meta["curve_tag"], "tag2")
        self.assertEqual(meta["cp_index"], "5")
        self.assertEqual(meta["point"], "relative_center")
        self.base.render.getRelativePoint.assert_called_once()

    def test_priority_distance_depth_curve(self):
        entry = self._make_mock_entry({"pick_kind": "curve"}, depth=8.0)
        priority, dist, depth = self.picker._get_priority_distance_depth(entry, Point2(0, 0))
        self.assertEqual(priority, 1)
        self.assertEqual(dist, 0.0)
        self.assertEqual(depth, 8.0)

    def test_priority_distance_depth_cp_with_projection(self):
        entry = self._make_mock_entry({"pick_kind": "cp"}, depth=5.0)
        solid = MagicMock()
        entry.getInto.return_value = solid

        def mock_project(pt_3d, pt_2d):
            pt_2d.setX(2.0)
            pt_2d.setY(3.0)
            return True

        self.base.camLens.project.side_effect = mock_project

        priority, dist, depth = self.picker._get_priority_distance_depth(entry, Point2(1.0, 1.0))

        self.assertEqual(priority, 0)
        # dist_sq = (2-1)^2 + (3-1)^2 = 1 + 4 = 5
        self.assertAlmostEqual(dist, 5.0)
        self.assertEqual(depth, 5.0)


if __name__ == "__main__":
    unittest.main()