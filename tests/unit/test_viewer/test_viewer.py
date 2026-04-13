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

class TestViewerDefaultOnHover(unittest.TestCase):
    """Tests pour le comportement par défaut au survol (HUD et surbrillance)."""

    def _make_viewer_with_mocks(self):
        """Crée un Viewer avec tous les mocks nécessaires pour tester l'interface."""
        from bot.viewer.viewer import Viewer
        viewer = Viewer()

        viewer._conn = MagicMock()

        viewer.highlight_curve = MagicMock()
        viewer.set_hud_text = MagicMock()

        mock_model = MagicMock()
        viewer.model = mock_model

        return viewer

    def test_default_on_hover_valid_tag(self):
        viewer = self._make_viewer_with_mocks()

        viewer.model.get_end_points.return_value = [10, 20]
        viewer.model.get_point_coords.side_effect = lambda tag: [0.0, 0.0, 0.0] if tag == 10 else [1.0, 1.0, 1.0]

        viewer._default_on_hover("1")

        viewer.model.get_end_points.assert_called_once_with(1)
        viewer.highlight_curve.assert_called_once_with("1", [1, 0.5, 0, 1])

        args, _ = viewer.set_hud_text.call_args
        texte_affiche = args[0]
        self.assertIn("Courbe 1", texte_affiche)
        self.assertIn("(0.00, 0.00, 0.00)", texte_affiche)
        self.assertIn("(1.00, 1.00, 1.00)", texte_affiche)

        self.assertEqual(viewer._default_last_hovered, "1")

    def test_default_on_hover_empty_space(self):
        viewer = self._make_viewer_with_mocks()
        viewer._default_last_hovered = "2"

        viewer._default_on_hover(None)

        viewer.highlight_curve.assert_called_once_with("2", [1, 1, 1, 1])
        viewer.set_hud_text.assert_called_once_with("Prêt. Survolez ou cliquez sur les courbes.")
        self.assertIsNone(viewer._default_last_hovered)

    def test_default_on_hover_change_curve(self):
        viewer = self._make_viewer_with_mocks()
        viewer._default_last_hovered = "1"
        viewer.model.get_end_points.return_value = [10, 20]
        viewer.model.get_point_coords.return_value = [0.0, 0.0, 0.0]

        viewer._default_on_hover("3")

        viewer.highlight_curve.assert_any_call("1", [1, 1, 1, 1])
        viewer.highlight_curve.assert_any_call("3", [1, 0.5, 0, 1])
        self.assertEqual(viewer._default_last_hovered, "3")

    def test_default_on_hover_invalid_tag(self):
        viewer = self._make_viewer_with_mocks()
        viewer._default_on_hover("tag_bizarre")
        viewer.highlight_curve.assert_called_once_with("tag_bizarre", [1, 0.5, 0, 1])

        args, _ = viewer.set_hud_text.call_args
        self.assertIn("invalid literal", args[0])


if __name__ == '__main__':
    unittest.main()
