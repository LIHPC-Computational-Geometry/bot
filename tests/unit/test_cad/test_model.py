"""
Unit tests for bot.core.cad.CADModel.

These tests cover observer notification, CADAdapter delta load, add_point
side-effects and input-validation errors on getClosestPoint.
"""

import unittest

from bot.core.cad import CADModel
from bot.viewer.adapters.adapter_cad import CADAdapter
from bot.viewer.contracts import SceneUpdateOp
from bot.viewer.tags import CAD_NS, encode, prefix


class _MockObserver:
    """Minimal observer that records every update() call."""

    def __init__(self):
        self.calls = []

    def update(self, model):
        self.calls.append(model)


class TestObserverPattern(unittest.TestCase):
    def setUp(self):
        self.model = CADModel()

    def tearDown(self):
        self.model.finalize()

    def test_add_point_notifies_observer(self):
        obs = _MockObserver()
        self.model.add_observer(obs)
        self.model.add_point([1.0, 1.0, 1.0])
        self.assertEqual(len(obs.calls), 1)
        self.assertIs(obs.calls[0], self.model)

    def test_add_point_notifies_all_observers(self):
        observers = [_MockObserver() for _ in range(3)]
        for obs in observers:
            self.model.add_observer(obs)
        self.model.add_point([0.0, 0.0, 0.0])
        for obs in observers:
            self.assertEqual(len(obs.calls), 1)
            self.assertIs(obs.calls[0], self.model)

    def test_remove_observer_stops_notifications(self):
        obs = _MockObserver()
        self.model.add_observer(obs)
        self.model.remove_observer(obs)
        self.model.add_point([1.0, 1.0, 1.0])
        self.assertEqual(len(obs.calls), 0)

    def test_each_mutation_notifies_observers(self):
        obs = _MockObserver()
        self.model.add_observer(obs)
        for i in range(3):
            self.model.add_point([float(i), 0.0, 0.0])
        self.assertEqual(len(obs.calls), 3)


class TestCADAdapterDeltaLoad(unittest.TestCase):
    """Render data is produced by CADAdapter, not CADModel directly."""

    def setUp(self):
        self.model = CADModel()
        self.model.open("data/profil_1.geo")

    def tearDown(self):
        self.model.finalize()

    def test_adapter_add_payload_has_required_keys(self):
        adapter = CADAdapter(self.model)
        data = adapter.get_delta_load()
        self.assertEqual(data["op"], SceneUpdateOp.ADD)
        self.assertIn("changed_curves", data)
        self.assertIn("bounds", data)
        self.assertIn("points", data)
        self.assertIn("edges", data)

    def test_changed_curves_match_model_topology(self):
        adapter = CADAdapter(self.model)
        data = adapter.get_delta_load()
        expected = {encode(CAD_NS, tag) for tag in self.model.get_curve_tags()}
        self.assertEqual(set(data["changed_curves"].keys()), expected)
        for tag in data["changed_curves"]:
            self.assertEqual(prefix(tag), CAD_NS)

    def test_bounds_match_model(self):
        bounds = CADAdapter(self.model).get_delta_load()["bounds"]
        self.assertEqual(bounds, self.model.bounds)
        for key in ("min", "max", "center", "size"):
            self.assertIn(key, bounds)


class TestAddPoint(unittest.TestCase):
    def setUp(self):
        self.model = CADModel()

    def tearDown(self):
        self.model.finalize()

    def test_add_point_returns_integer_tag(self):
        tag = self.model.add_point([1.0, 2.0, 3.0])
        self.assertIsInstance(tag, int)

    def test_add_point_increases_point_count(self):
        before = len(self.model.get_point_tags())
        self.model.add_point([0.0, 0.0, 0.0])
        after = len(self.model.get_point_tags())
        self.assertEqual(after, before + 1)

    def test_add_point_updates_bounds(self):
        coords = [10.0, 20.0, 30.0]
        self.model.add_point(coords)
        bounds = self.model.bounds
        for axis, value in enumerate(coords):
            self.assertLessEqual(bounds["min"][axis], value)
            self.assertGreaterEqual(bounds["max"][axis], value)


class TestGetClosestPointValidation(unittest.TestCase):
    def setUp(self):
        self.model = CADModel()
        self.model.open("data/profil_1.geo")

    def tearDown(self):
        self.model.finalize()

    def test_raises_type_error_for_non_int_dim(self):
        with self.assertRaises(TypeError):
            self.model.getClosestPoint(1.0, 1, [0, 0, 0])

    def test_raises_type_error_for_non_int_tag(self):
        with self.assertRaises(TypeError):
            self.model.getClosestPoint(1, "1", [0, 0, 0])

    def test_raises_type_error_for_invalid_coord(self):
        with self.assertRaises(TypeError):
            self.model.getClosestPoint(1, 1, "not_a_list")

    def test_raises_type_error_for_coord_wrong_length(self):
        with self.assertRaises(TypeError):
            self.model.getClosestPoint(1, 1, [0, 0])  # must be multiple of 3

    def test_raises_value_error_for_dim_out_of_range(self):
        with self.assertRaises(ValueError):
            self.model.getClosestPoint(0, 1, [0, 0, 0])

    def test_raises_value_error_for_dim_3(self):
        with self.assertRaises(ValueError):
            self.model.getClosestPoint(3, 1, [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
