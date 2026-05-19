import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    from bot.control.picker import RayPicker
    from panda3d.core import Point2, Point3

    _HAS_PANDA_DEPS = True
except ModuleNotFoundError:
    RayPicker = None
    _HAS_PANDA_DEPS = False


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestRayPicker(unittest.TestCase):
    """Test suite for the RayPicker class handling 3D object selection."""

    def setUp(self):
        self.base = MagicMock()
        if _HAS_PANDA_DEPS:
            from panda3d.core import NodePath

            # Simulate attachNewNode by wrapping the CollisionNode in a real NodePath
            self.base.camera.attachNewNode.side_effect = lambda node: NodePath(node)

        self.picker = RayPicker(self.base)

    def test_init_sets_masks_and_colliders(self):
        """Tests that RayPicker initializes the correct collision masks and colliders."""
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
        """Tests behavior when no collision entries are found by the traverser."""
        self.picker.queue = MagicMock()
        self.picker.queue.getNumEntries.return_value = 0
        self.picker.traverser = MagicMock()
        self.picker.picker_ray = MagicMock()

        result = self.picker.pick_entry(Point2(0, 0), "cp")
        self.assertIsNone(result)
        self.picker.traverser.traverse.assert_called_once_with(self.base.render)

    def test_pick_entry_wrong_kind(self):
        """Tests that pick_entry ignores collisions that don't match the expected kind."""
        entry = self._make_mock_entry({"pick_kind": "curve"})

        self.picker.queue = MagicMock()
        self.picker.queue.getNumEntries.return_value = 1
        self.picker.queue.getEntry.return_value = entry
        self.picker.traverser = MagicMock()
        self.picker.picker_ray = MagicMock()

        result = self.picker.pick_entry(Point2(0, 0), "cp")
        self.assertIsNone(result)

    def test_pick_entry_success_with_priority_sorting(self):
        """Verifies that control points (CP) have priority over curves without mocking the sorting function."""
        # Define arbitrary depths.
        # The curve is further away (10.0) than the CP (5.0).
        entry_curve = self._make_mock_entry({"pick_kind": "curve"}, depth=10.0)
        entry_cp = self._make_mock_entry({"pick_kind": "cp"}, depth=5.0)

        # Essential configuration so the *real* project() function executes
        solid = MagicMock()
        entry_cp.getInto.return_value = solid
        self.base.render.getRelativePoint.return_value = Point3(1, 1, 1)

        def mock_project(pt_3d, pt_2d):
            # Simulate that the projection places the point at 2D position (1.0, 1.0)
            pt_2d.setX(1.0)
            pt_2d.setY(1.0)
            return True

        self.base.camLens.project.side_effect = mock_project

        self.picker.queue = MagicMock()
        self.picker.queue.getNumEntries.return_value = 2
        self.picker.queue.getEntry.side_effect = [entry_curve, entry_cp]
        self.picker.traverser = MagicMock()
        self.picker.picker_ray = MagicMock()

        # Call the RayPicker with a simulated click at (0, 0)
        result = self.picker.pick_entry(Point2(0, 0), "cp")

        # The CP should win because sorting is tested with real math!
        self.assertEqual(result, entry_cp)

    def test_priority_distance_depth_cp_project_fails(self):
        """Verifies robustness if a point is outside the camera's field of view (project returns False)."""
        entry = self._make_mock_entry({"pick_kind": "cp"}, depth=5.0)
        solid = MagicMock()
        entry.getInto.return_value = solid

        # Simulate Panda3D failing to project the 3D point into 2D
        self.base.camLens.project.return_value = False

        priority, dist, depth = self.picker._get_priority_distance_depth(
            entry, Point2(1.0, 1.0)
        )

        # Verify that the fallback safety value (0, 0.0, depth) is applied
        self.assertEqual(priority, 0)
        self.assertEqual(dist, 0.0)
        self.assertEqual(depth, 5.0)

    def test_get_metadata_curve(self):
        """Tests extracting metadata from a curve collision entry."""
        entry = self._make_mock_entry({"pick_kind": "curve", "curve_tag": "tag1"})
        entry.getSurfacePoint.return_value = "surface_point"

        meta = self.picker.get_metadata(entry)
        self.assertEqual(meta["pick_kind"], "curve")
        self.assertEqual(meta["curve_tag"], "tag1")
        self.assertIsNone(meta["cp_index"])
        self.assertEqual(meta["point"], "surface_point")

    def test_get_metadata_cp_with_center(self):
        """Tests extracting metadata from a control point collision entry, including center calculation."""
        entry = self._make_mock_entry(
            {"pick_kind": "cp", "curve_tag": "tag2", "cp_index": "5"}
        )
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
        """Tests the priority and distance calculation for a curve entry."""
        entry = self._make_mock_entry({"pick_kind": "curve"}, depth=8.0)
        priority, dist, depth = self.picker._get_priority_distance_depth(
            entry, Point2(0, 0)
        )
        self.assertEqual(priority, 1)
        self.assertEqual(dist, 0.0)
        self.assertEqual(depth, 8.0)

    def test_priority_distance_depth_cp_with_projection(self):
        """Tests the priority and distance calculation for a control point with successful 2D projection."""
        entry = self._make_mock_entry({"pick_kind": "cp"}, depth=5.0)
        solid = MagicMock()
        entry.getInto.return_value = solid

        def mock_project(pt_3d, pt_2d):
            pt_2d.setX(2.0)
            pt_2d.setY(3.0)
            return True

        self.base.camLens.project.side_effect = mock_project

        priority, dist, depth = self.picker._get_priority_distance_depth(
            entry, Point2(1.0, 1.0)
        )

        self.assertEqual(priority, 0)
        # dist_sq = (2-1)^2 + (3-1)^2 = 1 + 4 = 5
        self.assertAlmostEqual(dist, 5.0)
        self.assertEqual(depth, 5.0)


if __name__ == "__main__":
    unittest.main()
