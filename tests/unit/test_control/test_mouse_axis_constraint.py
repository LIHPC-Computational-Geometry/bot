import sys
import unittest
from pathlib import Path

from panda3d.core import Plane, Point2, Point3, Vec3

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from unittest.mock import MagicMock

try:
    from bot.control.mouse import MouseHandler
    from bot.math.constraints import ConstraintManager

    _HAS_PANDA_DEPS = True
except ModuleNotFoundError:
    MouseHandler = None
    _HAS_PANDA_DEPS = False


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestMouseAxisConstraint(unittest.TestCase):
    """Test suite for the _apply_axis_constraint fallback method in ConstraintManager."""

    def _make_handler(self, mask: int):
        """Helper to create a MouseHandler with a specific axis constraint mask."""
        handler = MouseHandler.__new__(MouseHandler)
        handler.constraints = ConstraintManager(None)
        handler.constraints.set_axis_constraint(mask)
        return handler

    def test_mask_zero_blocks_all_axes(self):
        """Tests that mask 0 (no axes) returns the start position."""
        handler = self._make_handler(0)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(
            handler.constraints._apply_axis_constraint(start, candidate), start
        )

    def test_mask_four_keeps_only_z(self):
        """Tests that mask 4 (Z-axis only) replaces X and Y with the start position."""
        handler = self._make_handler(4)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(
            handler.constraints._apply_axis_constraint(start, candidate),
            [1.0, 2.0, 7.0],
        )

    def test_mask_three_keeps_xy(self):
        """Tests that mask 3 (XY-plane) replaces Z with the start position."""
        handler = self._make_handler(3)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(
            handler.constraints._apply_axis_constraint(start, candidate),
            [9.0, 8.0, 3.0],
        )

    def test_mask_seven_keeps_all_axes(self):
        """Tests that mask 7 (all axes) returns the candidate position unmodified."""
        handler = self._make_handler(7)
        start = [1.0, 2.0, 3.0]
        candidate = [9.0, 8.0, 7.0]
        self.assertEqual(
            handler.constraints._apply_axis_constraint(start, candidate), candidate
        )


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestConstraintManager(unittest.TestCase):
    """Test suite for ConstraintManager mathematics and projection logic."""

    def setUp(self):
        # Mocking base for ConstraintManager
        mock_base = MagicMock()
        self.manager = ConstraintManager(mock_base)
        if _HAS_PANDA_DEPS:
            # Default mock for getRelativeVector
            self.manager.base.render.getRelativeVector.return_value = Vec3(0, 0.5, 0)

    def test_set_axis_constraint_clamping(self):
        """Tests that the constraint mask is clamped between 0 and 7."""
        self.manager.set_axis_constraint(10)
        self.assertEqual(self.manager.axis_constraint_mask, 7)
        self.manager.set_axis_constraint(-5)
        self.assertEqual(self.manager.axis_constraint_mask, 0)

    def test_plane_normal_from_mask(self):
        """Tests the correct plane normal vector generation from bitmasks."""
        # XY Plane
        norm_xy = self.manager._plane_normal_from_mask(3)
        self.assertEqual(norm_xy.getZ(), 1)
        # XZ Plane
        norm_xz = self.manager._plane_normal_from_mask(5)
        self.assertEqual(norm_xz.getY(), 1)
        # YZ Plane
        norm_yz = self.manager._plane_normal_from_mask(6)
        self.assertEqual(norm_yz.getX(), 1)
        # Invalid
        self.assertIsNone(self.manager._plane_normal_from_mask(7))

    def test_build_drag_plane(self):
        """Tests the creation of a Panda3D Plane facing the camera from a start point."""
        start_point = Point3(1, 2, 3)
        plane = self.manager.build_drag_plane(start_point)

        self.assertEqual(plane.getNormal().getX(), 0)
        self.assertEqual(plane.getNormal().getY(), 1)
        self.assertEqual(plane.getNormal().getZ(), 0)

        # Using distToPlane to assert the point intersects perfectly with the origin location
        self.assertAlmostEqual(plane.distToPlane(start_point), 0.0)

    def test_closest_point_on_axis_to_ray_orthogonal_skew(self):
        """
        Tests two skew lines that are orthogonal.
        Ray: Y-axis. Axis: a line parallel to Z-axis at (1,0,0).
        Closest point on the axis should be (1,0,0).
        """
        hit = self.manager._closest_point_on_axis_to_ray(
            Point3(0, 0, 0), Vec3(0, 1, 0), Point3(1, 0, 0), Vec3(0, 0, 1)
        )
        self.assertEqual(hit, [1.0, 0.0, 0.0])

    def test_closest_point_on_axis_to_ray_parallel(self):
        """Tests two parallel lines, which should not have a unique closest point."""
        hit = self.manager._closest_point_on_axis_to_ray(
            Point3(0, 0, 0), Vec3(1, 0, 0), Point3(0, 1, 0), Vec3(1, 0, 0)
        )
        self.assertIsNone(hit)

    def test_closest_point_on_axis_to_ray_intersecting(self):
        """Tests two lines that intersect at (1,1,0)."""
        hit = self.manager._closest_point_on_axis_to_ray(
            Point3(0, 0, 0), Vec3(1, 1, 0), Point3(1, 0, 0), Vec3(0, 1, 0)
        )
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit[0], 1.0)
        self.assertAlmostEqual(hit[1], 1.0)
        self.assertAlmostEqual(hit[2], 0.0)

    def test_closest_point_on_axis_to_ray_general_skew(self):
        """
        Tests two general skew lines.
        Ray: line parallel to Y-axis at (10,0,0).
        Axis: line parallel to Z-axis at (0,5,0).
        Closest point on the axis should be (0,5,0).
        """
        hit = self.manager._closest_point_on_axis_to_ray(
            Point3(10, 0, 0), Vec3(0, 1, 0), Point3(0, 5, 0), Vec3(0, 0, 1)
        )
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit[0], 0.0)
        self.assertAlmostEqual(hit[1], 5.0)
        self.assertAlmostEqual(hit[2], 0.0)

    def test_mouse_to_constrained_axis_none_if_no_start_pos(self):
        """Tests that projection returns None if no drag start position is set."""
        self.manager.drag_start_world_pos = None
        self.assertIsNone(self.manager.mouse_to_constrained_axis((0, 0)))

    def test_mouse_to_constrained_axis_returns_start_when_mask_zero(self):
        """Tests that projection returns the start position when the mask is 0."""
        self.manager.drag_start_world_pos = [1, 2, 3]
        self.manager.drag_active_mask = 0
        result = self.manager.mouse_to_constrained_axis(Point2(0, 0))
        self.assertEqual(result, [1, 2, 3])

    def test_mouse_to_constrained_axis_calls_plane_when_mask_seven(self):
        """Tests that projection delegates to plane intersection when the mask is 7."""
        self.manager.drag_start_world_pos = [1.0, 2.0, 3.0]
        self.manager.drag_active_mask = 7
        self.manager._mouse_to_plane = MagicMock(return_value=[9.0, 8.0, 7.0])
        result = self.manager.mouse_to_constrained_axis(Point2(0, 0))
        self.assertEqual(result, [9.0, 8.0, 7.0])
        self.manager._mouse_to_plane.assert_called_once()

    def test_mouse_to_constrained_axis_returns_none_if_ray_fails(self):
        """Tests that projection returns None if mouse ray casting fails."""
        self.manager.drag_start_world_pos = [1.0, 2.0, 3.0]
        self.manager.drag_active_mask = 1
        self.manager._mouse_to_ray = MagicMock(return_value=(None, None))
        self.assertIsNone(self.manager.mouse_to_constrained_axis(Point2(0, 0)))

    def test_mouse_to_constrained_axis_single_axis_success(self):
        """Tests single-axis projection when the ray successfully gets close to the axis."""
        self.manager.drag_start_world_pos = [1.0, 2.0, 3.0]
        self.manager.drag_active_mask = 1  # X-axis
        self.manager._mouse_to_ray = MagicMock(
            return_value=(Point3(0, 0, 0), Vec3(1, 0, 0))
        )
        self.manager._closest_point_on_axis_to_ray = MagicMock(
            return_value=[5.0, 2.0, 3.0]
        )
        result = self.manager.mouse_to_constrained_axis(Point2(0, 0))
        self.assertEqual(result, [5.0, 2.0, 3.0])
        self.manager._closest_point_on_axis_to_ray.assert_called_once()

    def test_mouse_to_constrained_axis_single_axis_fallback(self):
        """Tests fallback to plane projection when single-axis projection fails."""
        self.manager.drag_start_world_pos = [1.0, 2.0, 3.0]
        self.manager.drag_active_mask = 2  # Y-axis
        self.manager._mouse_to_ray = MagicMock(
            return_value=(Point3(0, 0, 0), Vec3(1, 0, 0))
        )
        self.manager._closest_point_on_axis_to_ray = MagicMock(return_value=None)
        self.manager._mouse_to_plane = MagicMock(return_value=[0, 0, 0])
        self.manager._apply_axis_constraint = MagicMock(return_value=[1.0, 9.0, 3.0])

        result = self.manager.mouse_to_constrained_axis(Point2(0, 0))
        self.assertEqual(result, [1.0, 9.0, 3.0])
        self.manager._apply_axis_constraint.assert_called_once()

    def test_mouse_to_constrained_axis_plane_success(self):
        """Tests plane intersection projection for 2-axis masks (e.g., XY plane)."""
        self.manager.drag_start_world_pos = [1.0, 2.0, 3.0]
        self.manager.drag_active_mask = 3  # XY plane (Normal Z)
        # Ray straight down Z axis from (5, 5, 10) to the plane at Z=3
        self.manager._mouse_to_ray = MagicMock(
            return_value=(Point3(5.0, 5.0, 10.0), Vec3(0, 0, -1))
        )

        result = self.manager.mouse_to_constrained_axis(Point2(0, 0))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 5.0)
        self.assertAlmostEqual(result[1], 5.0)
        self.assertAlmostEqual(result[2], 3.0)

    def test_mouse_to_constrained_axis_plane_fallback(self):
        """Tests fallback to base constraint application when plane intersection fails."""
        self.manager.drag_start_world_pos = [1.0, 2.0, 3.0]
        self.manager.drag_active_mask = 3  # XY plane
        # Ray parallel to XY plane (e.g., along X axis) won't intersect
        self.manager._mouse_to_ray = MagicMock(
            return_value=(Point3(0, 0, 10), Vec3(1, 0, 0))
        )
        self.manager._mouse_to_plane = MagicMock(return_value=[0, 0, 0])
        self.manager._apply_axis_constraint = MagicMock(return_value=[4.0, 4.0, 3.0])

        result = self.manager.mouse_to_constrained_axis(Point2(0, 0))
        self.assertEqual(result, [4.0, 4.0, 3.0])
        self.manager._apply_axis_constraint.assert_called_once()

    def test_mouse_to_plane_no_drag_plane(self):
        """Tests that plane intersection returns None if no drag plane is defined."""
        self.manager.drag_plane = None
        result = self.manager._mouse_to_plane(Point2(0, 0))
        self.assertIsNone(result)

    def test_mouse_to_plane_ray_fails(self):
        """Tests that plane intersection returns None if mouse ray casting fails."""
        self.manager.drag_plane = Plane(Vec3(0, 1, 0), Point3(0, 0, 0))
        self.manager._mouse_to_ray = MagicMock(return_value=(None, None))
        result = self.manager._mouse_to_plane(Point2(0, 0))
        self.assertIsNone(result)

    def test_mouse_to_plane_intersection_succeeds(self):
        """Tests successful ray intersection with the drag plane."""
        # Plane is the XZ plane at Y=5
        self.manager.drag_plane = Plane(Vec3(0, 1, 0), Point3(0, 5, 0))

        # Ray starts at (0,0,0) and goes along the Y axis
        self.manager._mouse_to_ray = MagicMock(
            return_value=(Point3(0, 0, 0), Vec3(0, 1, 0))
        )

        result = self.manager._mouse_to_plane(Point2(0, 0))

        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 0.0)
        self.assertAlmostEqual(result[1], 5.0)
        self.assertAlmostEqual(result[2], 0.0)

    def test_mouse_to_plane_no_intersection(self):
        """Tests that plane intersection returns None if the ray is parallel to the plane."""
        # Plane is the XZ plane at Y=5
        self.manager.drag_plane = Plane(Vec3(0, 1, 0), Point3(0, 5, 0))

        # Ray starts at (0,0,0) and goes along the X axis (parallel to plane)
        self.manager._mouse_to_ray = MagicMock(
            return_value=(Point3(0, 0, 0), Vec3(1, 0, 0))
        )

        result = self.manager._mouse_to_plane(Point2(0, 0))
        self.assertIsNone(result)

    def test_mouse_to_ray_extrude_fails(self):
        """Tests that _mouse_to_ray returns None when camLens.extrude fails."""
        self.manager.base.cam.node().getLens().extrude.return_value = False
        origin, direction = self.manager._mouse_to_ray(Point2(0, 0))
        self.assertIsNone(origin)
        self.assertIsNone(direction)
        self.manager.base.cam.node().getLens().extrude.assert_called_once()

    def test_mouse_to_ray_succeeds_general_case(self):
        """
        Tests _mouse_to_ray with a successful extrusion where the ray is not
        parallel to the camera's XY plane.
        """

        # This simulates the extrude method filling in p_from and p_to
        def mock_extrude(m_pos, p_from, p_to):
            p_from.x, p_from.y, p_from.z = 0, -10, 0
            p_to.x, p_to.y, p_to.z = 0, 10, 0
            return True

        self.manager.base.cam.node().getLens().extrude.side_effect = mock_extrude

        # Mock coordinate system transforms to be identity for simplicity
        self.manager.base.render.getRelativePoint.side_effect = lambda cam, point: point
        self.manager.base.render.getRelativeVector.side_effect = lambda cam, vec: vec

        origin, direction = self.manager._mouse_to_ray(Point2(0.5, 0.5))

        self.assertIsNotNone(origin)
        self.assertIsNotNone(direction)
        self.assertAlmostEqual(origin.x, 0)
        self.assertAlmostEqual(origin.y, 0)
        self.assertAlmostEqual(origin.z, 0)
        self.assertAlmostEqual(direction.x, 0)
        self.assertAlmostEqual(direction.y, 1)
        self.assertAlmostEqual(direction.z, 0)

    def test_mouse_to_ray_succeeds_y_is_zero(self):
        """
        Tests _mouse_to_ray with a successful extrusion where the ray is
        parallel to the camera's XY plane (dir_cam.y is zero).
        """

        def mock_extrude(m_pos, p_from, p_to):
            p_from.x, p_from.y, p_from.z = -10, 5, 0
            p_to.x, p_to.y, p_to.z = 10, 5, 0
            return True

        self.manager.base.cam.node().getLens().extrude.side_effect = mock_extrude
        self.manager.base.render.getRelativePoint.side_effect = lambda cam, point: point
        self.manager.base.render.getRelativeVector.side_effect = lambda cam, vec: vec

        origin, direction = self.manager._mouse_to_ray(Point2(0.5, 0.5))

        self.assertIsNotNone(origin)
        self.assertIsNotNone(direction)
        self.assertAlmostEqual(origin.x, -10)
        self.assertAlmostEqual(origin.y, 5)
        self.assertAlmostEqual(origin.z, 0)
        self.assertAlmostEqual(direction.x, 1)
        self.assertAlmostEqual(direction.y, 0)
        self.assertAlmostEqual(direction.z, 0)


if __name__ == "__main__":
    unittest.main()
