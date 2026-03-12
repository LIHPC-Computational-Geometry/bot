"""
Unit tests for bot.viewer.viewer.Viewer.

The subprocess and multiprocessing pipe are fully mocked so these tests
run without Panda3D or a display.
"""
import unittest
from unittest.mock import MagicMock, patch, PropertyMock


class _FakeModel:
    """Minimal Model stand-in for observer-registration tests."""
    def __init__(self):
        self._observers = []

    def add_observer(self, obs):
        self._observers.append(obs)

    def remove_observer(self, obs):
        self._observers.remove(obs)

    def get_render_data(self):
        return {'points': [], 'edges': [], 'bounds': {}}


class TestViewerConnect(unittest.TestCase):

    def _make_viewer(self):
        from bot.viewer.viewer import Viewer
        return Viewer()

    def test_connect_registers_viewer_as_observer(self):
        viewer = self._make_viewer()
        model = _FakeModel()
        viewer.connect(model)
        self.assertIn(viewer, model._observers)

    def test_connect_stores_model_reference(self):
        viewer = self._make_viewer()
        model = _FakeModel()
        viewer.connect(model)
        self.assertIs(viewer.model, model)

    def test_connect_returns_self_for_chaining(self):
        viewer = self._make_viewer()
        model = _FakeModel()
        result = viewer.connect(model)
        self.assertIs(result, viewer)

    def test_connect_replaces_previous_model(self):
        viewer = self._make_viewer()
        model1 = _FakeModel()
        model2 = _FakeModel()
        viewer.connect(model1)
        viewer.connect(model2)
        self.assertNotIn(viewer, model1._observers)
        self.assertIn(viewer, model2._observers)
        self.assertIs(viewer.model, model2)


class TestViewerDisconnect(unittest.TestCase):

    def _make_viewer(self):
        from bot.viewer.viewer import Viewer
        return Viewer()

    def test_disconnect_removes_observer(self):
        viewer = self._make_viewer()
        model = _FakeModel()
        viewer.connect(model)
        viewer.disconnect()
        self.assertNotIn(viewer, model._observers)

    def test_disconnect_clears_model_reference(self):
        viewer = self._make_viewer()
        model = _FakeModel()
        viewer.connect(model)
        viewer.disconnect()
        self.assertIsNone(viewer.model)

    def test_disconnect_returns_self_for_chaining(self):
        viewer = self._make_viewer()
        model = _FakeModel()
        viewer.connect(model)
        result = viewer.disconnect()
        self.assertIs(result, viewer)

    def test_disconnect_without_model_is_safe(self):
        viewer = self._make_viewer()
        # Should not raise even when no model is connected
        viewer.disconnect()


class TestViewerUpdate(unittest.TestCase):

    def _make_viewer(self):
        from bot.viewer.viewer import Viewer
        return Viewer()

    def test_update_sends_render_data_over_pipe(self):
        viewer = self._make_viewer()
        model = _FakeModel()

        mock_conn = MagicMock()
        viewer._conn = mock_conn

        viewer.update(model)

        mock_conn.send.assert_called_once_with(
            ('update', model.get_render_data())
        )

    def test_update_ignores_broken_pipe(self):
        viewer = self._make_viewer()
        model = _FakeModel()

        mock_conn = MagicMock()
        mock_conn.send.side_effect = BrokenPipeError
        viewer._conn = mock_conn

        # Should not raise
        viewer.update(model)

    def test_update_does_nothing_without_connection(self):
        viewer = self._make_viewer()
        model = _FakeModel()
        # _conn is None by default — must not raise
        viewer.update(model)


class TestViewerSend(unittest.TestCase):

    def _make_viewer(self):
        from bot.viewer.viewer import Viewer
        return Viewer()

    def test_send_transmits_command(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        viewer._conn = mock_conn
        viewer._send('load', {'points': []})
        mock_conn.send.assert_called_once_with(('load', {'points': []}))

    def test_send_silences_broken_pipe(self):
        viewer = self._make_viewer()
        mock_conn = MagicMock()
        mock_conn.send.side_effect = BrokenPipeError
        viewer._conn = mock_conn
        # Should not raise
        viewer._send('load', {})

    def test_send_noop_when_no_connection(self):
        viewer = self._make_viewer()
        # No exception expected
        viewer._send('load', {})


if __name__ == '__main__':
    unittest.main()
