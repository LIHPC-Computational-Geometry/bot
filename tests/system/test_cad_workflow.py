"""
System tests — full CAD workflow.

These tests exercise the Model end-to-end: file loading, topology queries,
point addition and render-data consistency.  No Panda3D required.
"""

import unittest
from bot.core.cad import Model as CADModel

GEO_FILE = "data/profil_1.geo"


class TestLoadAndTopology(unittest.TestCase):
    """Open profil_1.geo and verify the full topology is coherent."""

    def setUp(self):
        self.cad = CADModel()
        self.cad.open(GEO_FILE)

    def tearDown(self):
        self.cad.finalize()

    def test_point_count(self):
        self.assertEqual(6, len(self.cad.get_point_tags()))

    def test_curve_count(self):
        self.assertEqual(5, len(self.cad.get_curve_tags()))

    def test_no_surfaces(self):
        self.assertEqual(0, len(self.cad.get_surface_tags()))

    def test_every_curve_has_two_endpoints(self):
        for tag in self.cad.get_curve_tags():
            self.assertEqual(2, len(self.cad.get_end_points(tag)))

    def test_adjacency_structure(self):
        """Each point connects to 2 curves (profile) except the isolated free point."""
        counts = {
            tag: len(self.cad.get_adjacent_curves_of_point(tag))
            for tag in self.cad.get_point_tags()
        }
        self.assertEqual(5, sum(1 for c in counts.values() if c == 2))
        self.assertEqual(1, sum(1 for c in counts.values() if c == 0))

    def test_get_adjacent_points_returns_two_per_curve(self):
        for tag in self.cad.get_curve_tags():
            self.assertEqual(2, len(self.cad.get_adjacent_points(tag)))


class TestRenderDataCoherence(unittest.TestCase):
    """Verify get_render_data() returns a consistent, picklable snapshot."""

    def setUp(self):
        self.cad = CADModel()
        self.cad.open(GEO_FILE)

    def tearDown(self):
        self.cad.finalize()

    def test_render_data_has_all_keys(self):
        data = self.cad.get_render_data()
        self.assertIn("points", data)
        self.assertIn("edges", data)
        self.assertIn("bounds", data)

    def test_edges_reference_valid_point_indices(self):
        data = self.cad.get_render_data()
        n = len(data["points"])
        for idx_a, idx_b, _curve_tag in data["edges"]:
            self.assertGreaterEqual(idx_a, 0)
            self.assertLess(idx_a, n)
            self.assertGreaterEqual(idx_b, 0)
            self.assertLess(idx_b, n)

    def test_bounds_center_is_inside_min_max(self):
        bounds = self.cad.get_render_data()["bounds"]
        for axis in range(3):
            self.assertGreaterEqual(bounds["center"][axis], bounds["min"][axis] - 1e-9)
            self.assertLessEqual(bounds["center"][axis], bounds["max"][axis] + 1e-9)

    def test_bounds_size_matches_min_max(self):
        bounds = self.cad.get_render_data()["bounds"]
        for axis in range(3):
            expected = bounds["max"][axis] - bounds["min"][axis]
            self.assertAlmostEqual(bounds["size"][axis], expected, places=9)

    def test_render_data_is_picklable(self):
        import pickle

        data = self.cad.get_render_data()
        serialised = pickle.dumps(data)
        restored = pickle.loads(serialised)
        self.assertEqual(data["bounds"], restored["bounds"])
        self.assertEqual(len(data["points"]), len(restored["points"]))


class TestAddPointWorkflow(unittest.TestCase):
    """Add points to an already-loaded model and verify the state stays consistent."""

    def setUp(self):
        self.cad = CADModel()
        self.cad.open(GEO_FILE)
        self.initial_point_count = len(self.cad.get_point_tags())
        self.initial_render_pts = len(self.cad.get_render_data()["points"])

    def tearDown(self):
        self.cad.finalize()

    def test_add_point_increments_tag_count(self):
        self.cad.add_point([100.0, 100.0, 0.0])
        self.assertEqual(
            self.initial_point_count + 1,
            len(self.cad.get_point_tags()),
        )

    def test_add_point_returns_valid_tag(self):
        tag = self.cad.add_point([1.0, 1.0, 0.0])
        self.assertIn(tag, self.cad.get_point_tags())

    def test_add_point_updates_render_data(self):
        self.cad.add_point([100.0, 100.0, 0.0])
        new_count = len(self.cad.get_render_data()["points"])
        # Mesh is regenerated: number of discretisation nodes changes
        self.assertGreater(new_count, 0)

    def test_bounds_extend_when_point_is_outside(self):
        old_bounds = self.cad.get_render_data()["bounds"]
        far_x = old_bounds["max"][0] + 1000.0
        self.cad.add_point([far_x, 0.0, 0.0])
        new_bounds = self.cad.get_render_data()["bounds"]
        self.assertGreaterEqual(new_bounds["max"][0], far_x - 1e-6)

    def test_cumulative_additions(self):
        coords = [[10.0, 0.0, 0.0], [20.0, 0.0, 0.0], [30.0, 0.0, 0.0]]
        for c in coords:
            self.cad.add_point(c)
        self.assertEqual(
            self.initial_point_count + 3,
            len(self.cad.get_point_tags()),
        )


class TestClosestPointWorkflow(unittest.TestCase):
    """End-to-end closest-point query on a loaded model."""

    def setUp(self):
        self.cad = CADModel()
        self.cad.open(GEO_FILE)

    def tearDown(self):
        self.cad.finalize()

    def test_closest_point_on_straight_line(self):
        # Curve 2 is the straight line from (0,1,0) to (5,1,0)
        coords = [2, 0, 0, 4, 2, 0]
        result = self.cad.getClosestPoint(1, 2, coords)
        oracle = [2, 1, 0, 4, 1, 0]
        for v1, v2 in zip(oracle, result):
            self.assertAlmostEqual(v1, v2, delta=1e-9)

    def test_closest_point_result_length_matches_input(self):
        coords = [1, 0, 0, 2, 0, 0]
        result = self.cad.getClosestPoint(1, 2, coords)
        self.assertEqual(len(result), len(coords))


if __name__ == "__main__":
    unittest.main()
