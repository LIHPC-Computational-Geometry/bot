"""
System tests — Model → Viewer observer pipeline.

These tests exercise the complete notification chain:
  Model.add_point()  →  _notify_observers()  →  adapter  →  Viewer._on_delta()

The subprocess is not started (no Panda3D / no display required).
"""

import unittest
from unittest.mock import MagicMock

from bot.core.cad import CADModel
from bot.viewer.tags import CAD_NS, encode, prefix
from bot.viewer.contracts import SceneUpdateOp
from bot.viewer.viewer import Viewer

GEO_FILE = "data/profil_1.geo"


def _make_spied_viewer() -> tuple[Viewer, MagicMock]:
    """Return a Viewer whose pipe connection is replaced by a MagicMock spy."""
    viewer = Viewer()
    spy = MagicMock()
    viewer._conn = spy
    return viewer, spy


def _expected_curve_tags(model: CADModel) -> set[str]:
    return {encode(CAD_NS, tag) for tag in model.get_curve_tags()}


class TestViewerReceivesLoad(unittest.TestCase):
    """Connecting a Viewer to an already-loaded Model triggers an initial add."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)

    def tearDown(self):
        self.model.finalize()

    def test_connect_sends_add_command(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect_models(self.model)
        spy.send.assert_called_once()
        cmd, data = spy.send.call_args[0][0]
        self.assertEqual(cmd, SceneUpdateOp.ADD)
        self.assertEqual(data["op"], SceneUpdateOp.ADD)
        self.assertEqual(
            set(data["changed_curves"].keys()), _expected_curve_tags(self.model)
        )
        self.assertEqual(data["bounds"], self.model.bounds)
        for tag in data["changed_curves"]:
            self.assertEqual(prefix(tag), CAD_NS)
        self.assertIn("points", data)
        self.assertIn("edges", data)
        self.assertGreater(len(data["edges"]), 0)


class TestViewerReceivesUpdate(unittest.TestCase):
    """Mutating the Model propagates an update through the adapter chain."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)
        self.viewer, self.spy = _make_spied_viewer()
        self.viewer.connect_models(self.model)
        self.spy.reset_mock()  # ignore the initial 'add' call

    def tearDown(self):
        self.model.finalize()

    def test_add_point_triggers_update(self):
        self.model.add_point([50.0, 50.0, 0.0])
        self.spy.send.assert_called_once()
        cmd, data = self.spy.send.call_args[0][0]
        self.assertEqual(cmd, SceneUpdateOp.UPDATE)
        self.assertEqual(data["op"], SceneUpdateOp.UPDATE)
        self.assertEqual(
            set(data["changed_curves"].keys()), _expected_curve_tags(self.model)
        )

    def test_multiple_mutations_each_trigger_update(self):
        for x in [10.0, 20.0, 30.0]:
            self.model.add_point([x, 0.0, 0.0])
        self.assertEqual(3, self.spy.send.call_count)
        for c in self.spy.send.call_args_list:
            cmd, data = c[0][0]
            self.assertEqual(cmd, SceneUpdateOp.UPDATE)
            self.assertEqual(data["op"], SceneUpdateOp.UPDATE)
            self.assertEqual(
                set(data["changed_curves"].keys()), _expected_curve_tags(self.model)
            )


class TestMultipleViewers(unittest.TestCase):
    """All viewers connected to the same model receive every update."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)

    def tearDown(self):
        self.model.finalize()

    def test_two_viewers_both_receive_add(self):
        v1, spy1 = _make_spied_viewer()
        v2, spy2 = _make_spied_viewer()
        v1.connect_models(self.model)
        v2.connect_models(self.model)
        spy1.send.assert_called_once()
        spy2.send.assert_called_once()

    def test_two_viewers_both_receive_update(self):
        v1, spy1 = _make_spied_viewer()
        v2, spy2 = _make_spied_viewer()
        v1.connect_models(self.model)
        v2.connect_models(self.model)
        spy1.reset_mock()
        spy2.reset_mock()

        self.model.add_point([99.0, 99.0, 0.0])

        spy1.send.assert_called_once()
        spy2.send.assert_called_once()

    def test_disconnected_viewer_does_not_receive_update(self):
        v1, spy1 = _make_spied_viewer()
        v2, spy2 = _make_spied_viewer()
        v1.connect_models(self.model)
        v2.connect_models(self.model)
        v2.disconnect()
        spy1.reset_mock()
        spy2.reset_mock()

        self.model.add_point([99.0, 99.0, 0.0])

        spy1.send.assert_called_once()
        spy2.send.assert_not_called()


class TestViewerStopCleansUp(unittest.TestCase):
    """stop() detaches the viewer from adapters (not the model observers)."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)

    def tearDown(self):
        self.model.finalize()

    def test_disconnect_clears_viewable(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect_models(self.model)
        viewer.disconnect()
        self.assertIsNone(viewer._viewable)

    def test_after_disconnect_model_mutation_does_not_reach_viewer(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect_models(self.model)
        spy.reset_mock()
        viewer.disconnect()

        self.model.add_point([1.0, 1.0, 0.0])

        spy.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
