"""
Unit tests for bot.viewer.viewer.Viewer.

The subprocess and multiprocessing pipe are fully mocked so these tests
run without Panda3D or a display.
"""

import unittest
from unittest.mock import MagicMock


class _FakeViewable:
    """Minimal IViewable stand-in."""

    def __init__(self):
        self._callback = None
        self.bound = False
        self.unbound = False

    def bind_update(self, callback):
        self._callback = callback
        self.bound = True

    def unbind_update(self):
        self._callback = None
        self.unbound = True

    def get_delta_load(self):
        return {"op": "add", "changed_curves": {}}

    def handle_event(self, event):
        return []


class TestViewerConnect(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        return Viewer()

    def test_connect_binds_viewable(self):
        viewer = self._make_viewer()
        viewable = _FakeViewable()
        viewer._connect(viewable)
        self.assertTrue(viewable.bound)
        self.assertIs(viewer._viewable, viewable)

    def test_connect_returns_self_for_chaining(self):
        viewer = self._make_viewer()
        result = viewer._connect(_FakeViewable())
        self.assertIs(result, viewer)

    def test_connect_replaces_previous_viewable(self):
        viewer = self._make_viewer()
        v1 = _FakeViewable()
        v2 = _FakeViewable()
        viewer._connect(v1)
        viewer._connect(v2)
        self.assertTrue(v1.unbound)
        self.assertIs(viewer._viewable, v2)

    def test_connect_sends_add_when_pipe_open(self):
        viewer = self._make_viewer()
        viewer._conn = MagicMock()
        viewer._connect(_FakeViewable())
        viewer._conn.send.assert_called_with(
            ("add", {"op": "add", "changed_curves": {}})
        )


class TestViewerDisconnect(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        return Viewer()

    def test_disconnect_unbinds_viewable(self):
        viewer = self._make_viewer()
        viewable = _FakeViewable()
        viewer._connect(viewable)
        viewer.disconnect()
        self.assertTrue(viewable.unbound)
        self.assertIsNone(viewer._viewable)

    def test_disconnect_returns_self_for_chaining(self):
        viewer = self._make_viewer()
        viewer._connect(_FakeViewable())
        result = viewer.disconnect()
        self.assertIs(result, viewer)

    def test_disconnect_without_viewable_is_safe(self):
        viewer = self._make_viewer()
        viewer.disconnect()


class TestViewerPipe(unittest.TestCase):
    """IPC forwarding — one place for send / on_delta behaviour."""

    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        return Viewer()

    def test_forwards_message_when_connected(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        viewer._conn = mock_conn
        payload = {"op": "update", "changed_curves": {"cad:1": {}}}
        viewer._on_delta(payload)
        mock_conn.send.assert_called_once_with(("update", payload))

    def test_ignores_broken_pipe(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        mock_conn.send.side_effect = BrokenPipeError
        viewer._conn = mock_conn
        viewer._send("add", {})
        viewer._on_delta({"op": "update", "changed_curves": {}})

    def test_noop_when_no_connection(self):
        viewer = self._make_viewer()
        viewer._send("add", {})


class TestViewerAxisConstraint(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        viewer = Viewer()
        viewer._conn = MagicMock()
        return viewer

    def test_set_axis_constraint_clamps_invalid_value(self):
        viewer = self._make_viewer()
        viewer.set_axis_constraint("oops")
        viewer._conn.send.assert_called_with(("set_axis_constraint", {"mask": 7}))

    def test_set_axis_constraint_clamps_out_of_range(self):
        viewer = self._make_viewer()
        viewer.set_axis_constraint(99)
        viewer._conn.send.assert_called_with(("set_axis_constraint", {"mask": 7}))


class TestViewerMoveControlPoint(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        viewer = Viewer()
        viewer._conn = MagicMock()
        viewer.set_hud_text = MagicMock()
        return viewer

    def test_move_control_point_delegates_to_viewable(self):
        viewer = self._make_viewer()
        viewable = MagicMock()
        viewable.handle_event.return_value = []
        viewer._viewable = viewable
        viewer.move_control_point("spline:curve-1", 1, [1.0, 2.0, 3.0])
        viewable.handle_event.assert_called_once()
        event = viewable.handle_event.call_args[0][0]
        self.assertEqual(event["event_type"], "cp_pick_end")
        self.assertEqual(event["curve_tag"], "spline:curve-1")
        self.assertEqual(event["world_pos"], [1.0, 2.0, 3.0])


if __name__ == "__main__":
    unittest.main()
