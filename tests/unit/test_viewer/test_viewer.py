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
        viewer.connect(viewable)
        self.assertTrue(viewable.bound)
        self.assertIs(viewer._viewable, viewable)

    def test_connect_returns_self_for_chaining(self):
        viewer = self._make_viewer()
        result = viewer.connect(_FakeViewable())
        self.assertIs(result, viewer)

    def test_connect_replaces_previous_viewable(self):
        viewer = self._make_viewer()
        v1 = _FakeViewable()
        v2 = _FakeViewable()
        viewer.connect(v1)
        viewer.connect(v2)
        self.assertTrue(v1.unbound)
        self.assertIs(viewer._viewable, v2)

    def test_connect_sends_add_when_pipe_open(self):
        viewer = self._make_viewer()
        viewer._conn = MagicMock()
        viewer.connect(_FakeViewable())
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
        viewer.connect(viewable)
        viewer.disconnect()
        self.assertTrue(viewable.unbound)
        self.assertIsNone(viewer._viewable)

    def test_disconnect_returns_self_for_chaining(self):
        viewer = self._make_viewer()
        viewer.connect(_FakeViewable())
        result = viewer.disconnect()
        self.assertIs(result, viewer)

    def test_disconnect_without_viewable_is_safe(self):
        viewer = self._make_viewer()
        viewer.disconnect()


class TestViewerOnDelta(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        return Viewer()

    def test_on_delta_sends_op_over_pipe(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        viewer._conn = mock_conn
        viewer._on_delta({"op": "update", "changed_curves": {}})
        mock_conn.send.assert_called_once_with(
            ("update", {"op": "update", "changed_curves": {}})
        )

    def test_on_delta_ignores_broken_pipe(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        mock_conn.send.side_effect = BrokenPipeError
        viewer._conn = mock_conn
        viewer._on_delta({"op": "update", "changed_curves": {}})


class TestViewerSend(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        return Viewer()

    def test_send_transmits_command(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        viewer._conn = mock_conn
        viewer._send("add", {"op": "add", "changed_curves": {}})
        mock_conn.send.assert_called_once_with(
            ("add", {"op": "add", "changed_curves": {}})
        )

    def test_send_silences_broken_pipe(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        mock_conn.send.side_effect = BrokenPipeError
        viewer._conn = mock_conn
        viewer._send("add", {})

    def test_send_noop_when_no_connection(self):
        viewer = self._make_viewer()
        viewer._send("add", {})


class TestViewerDispatchCommands(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        viewer = Viewer()
        viewer._conn = MagicMock()
        viewer.highlight_curve = MagicMock()
        viewer.set_hud_text = MagicMock()
        viewer.set_edit_mode = MagicMock()
        viewer.set_active_curve = MagicMock()
        return viewer

    def test_dispatch_highlight_and_hud(self):
        viewer = self._make_viewer()
        viewer._dispatch_commands(
            [
                {"cmd": "highlight_curve", "tag": "cad:1", "color": [1, 0, 0, 1]},
                {"cmd": "update_hud", "text": "hello"},
            ]
        )
        viewer.highlight_curve.assert_called_once_with("cad:1", [1, 0, 0, 1])
        viewer.set_hud_text.assert_called_once_with("hello")

    def test_dispatch_edit_mode(self):
        viewer = self._make_viewer()
        viewer._dispatch_commands(
            [{"cmd": "set_edit_mode", "enabled": True, "curve_tag": "cad:2"}]
        )
        viewer.set_edit_mode.assert_called_once_with(True, "cad:2")


class TestViewerCurveEditMode(unittest.TestCase):
    def _make_viewer(self):
        from bot.viewer.viewer import Viewer

        viewer = Viewer()
        viewer._conn = MagicMock()
        return viewer

    def test_set_edit_mode_sends_command(self):
        viewer = self._make_viewer()
        viewer.set_edit_mode(True, "cad:7")
        viewer._conn.send.assert_called_with(
            ("set_edit_mode", {"enabled": True, "curve_tag": "cad:7"})
        )

    def test_set_active_curve_sends_command(self):
        viewer = self._make_viewer()
        viewer.set_active_curve("cad:9")
        viewer._conn.send.assert_called_with(
            ("set_active_curve", {"curve_tag": "cad:9"})
        )

    def test_set_axis_constraint_sends_command(self):
        viewer = self._make_viewer()
        viewer.set_axis_constraint(6)
        viewer._conn.send.assert_called_with(("set_axis_constraint", {"mask": 6}))

    def test_set_axis_constraint_clamps_invalid_value(self):
        viewer = self._make_viewer()
        viewer.set_axis_constraint("oops")
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


if __name__ == "__main__":
    unittest.main()
