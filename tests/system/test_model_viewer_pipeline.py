"""
System tests — Model → Viewer observer pipeline.

These tests exercise the complete notification chain:
  Model.add_point()  →  _notify_observers()  →  Viewer.update()  →  Viewer._send()

The subprocess is not started (no Panda3D / no display required).  The real pipe
endpoint is replaced by a spy so we can assert on what would have been transmitted
to the rendering process.
"""

import unittest
from unittest.mock import MagicMock

from bot.core.cad import Model as CADModel
from bot.viewer.viewer import Viewer

GEO_FILE = "data/profil_1.geo"


def _make_spied_viewer() -> tuple[Viewer, MagicMock]:
    """Return a Viewer whose pipe connection is replaced by a MagicMock spy."""
    viewer = Viewer()
    spy = MagicMock()
    viewer._conn = spy
    return viewer, spy


class TestViewerReceivesLoad(unittest.TestCase):
    """Connecting a Viewer to an already-loaded Model triggers an initial load."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)

    def tearDown(self):
        self.model.finalize()

    def test_connect_sends_load_command(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect(self.model)
        spy.send.assert_called_once()
        cmd, data = spy.send.call_args[0][0]
        self.assertEqual(cmd, "load")

    def test_load_payload_contains_points_and_edges(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect(self.model)
        _, data = spy.send.call_args[0][0]
        self.assertIn("points", data)
        self.assertIn("edges", data)
        self.assertGreater(len(data["points"]), 0)
        self.assertGreater(len(data["edges"]), 0)

    def test_load_payload_contains_bounds(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect(self.model)
        _, data = spy.send.call_args[0][0]
        self.assertIn("bounds", data)


class TestViewerReceivesUpdate(unittest.TestCase):
    """Mutating the Model propagates an update through the full observer chain."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)
        self.viewer, self.spy = _make_spied_viewer()
        self.viewer.connect(self.model)
        self.spy.reset_mock()  # ignore the initial 'load' call

    def tearDown(self):
        self.model.finalize()

    def test_add_point_triggers_update(self):
        self.model.add_point([50.0, 50.0, 0.0])
        self.spy.send.assert_called_once()
        cmd, _ = self.spy.send.call_args[0][0]
        self.assertEqual(cmd, "update")

    def test_update_payload_is_consistent_render_data(self):
        self.model.add_point([50.0, 50.0, 0.0])
        _, data = self.spy.send.call_args[0][0]
        self.assertIn("points", data)
        self.assertIn("edges", data)
        self.assertIn("bounds", data)

    def test_multiple_mutations_each_trigger_update(self):
        for x in [10.0, 20.0, 30.0]:
            self.model.add_point([x, 0.0, 0.0])
        self.assertEqual(3, self.spy.send.call_count)
        for c in self.spy.send.call_args_list:
            cmd, _ = c[0][0]
            self.assertEqual(cmd, "update")


class TestMultipleViewers(unittest.TestCase):
    """All viewers connected to the same model receive every update."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)

    def tearDown(self):
        self.model.finalize()

    def test_two_viewers_both_receive_load(self):
        v1, spy1 = _make_spied_viewer()
        v2, spy2 = _make_spied_viewer()
        v1.connect(self.model)
        v2.connect(self.model)
        spy1.send.assert_called_once()
        spy2.send.assert_called_once()

    def test_two_viewers_both_receive_update(self):
        v1, spy1 = _make_spied_viewer()
        v2, spy2 = _make_spied_viewer()
        v1.connect(self.model)
        v2.connect(self.model)
        spy1.reset_mock()
        spy2.reset_mock()

        self.model.add_point([99.0, 99.0, 0.0])

        spy1.send.assert_called_once()
        spy2.send.assert_called_once()

    def test_disconnected_viewer_does_not_receive_update(self):
        v1, spy1 = _make_spied_viewer()
        v2, spy2 = _make_spied_viewer()
        v1.connect(self.model)
        v2.connect(self.model)
        v2.disconnect()
        spy1.reset_mock()
        spy2.reset_mock()

        self.model.add_point([99.0, 99.0, 0.0])

        spy1.send.assert_called_once()
        spy2.send.assert_not_called()


class TestViewerStopCleansUp(unittest.TestCase):
    """stop() deregisters the viewer from the model."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)

    def tearDown(self):
        self.model.finalize()

    def test_stop_removes_viewer_from_observers(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect(self.model)
        # Simulate stop() without the real subprocess
        viewer._running = False
        viewer.disconnect()
        self.assertNotIn(viewer, self.model._observers)

    def test_after_stop_model_mutation_does_not_reach_viewer(self):
        viewer, spy = _make_spied_viewer()
        viewer.connect(self.model)
        spy.reset_mock()
        viewer.disconnect()

        self.model.add_point([1.0, 1.0, 0.0])

        spy.send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
