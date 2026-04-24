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

    def test_default_on_hover_empty_space(self):
        viewer = self._make_viewer_with_mocks()
        viewer._default_last_hovered = "2"

        viewer._default_on_hover(None)

        viewer.highlight_curve.assert_called_once_with("2", [1, 1, 1, 1])
        viewer.set_hud_text.assert_called_once_with("Prêt. Survolez ou cliquez sur les courbes.")
        self.assertIsNone(viewer._default_last_hovered)

    def test_default_on_hover_invalid_tag(self):
        viewer = self._make_viewer_with_mocks()
        viewer._default_on_hover("tag_bizarre")
        viewer.highlight_curve.assert_called_once_with("tag_bizarre", [1, 0.5, 0, 1])

        args, _ = viewer.set_hud_text.call_args
        self.assertIn("invalid literal", args[0])

    def test_default_on_hover_valid_tag(self):
        viewer = self._make_viewer_with_mocks()

        viewer.model.get_end_points_coords.return_value = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]

        viewer._default_on_hover("1")

        viewer.model.get_end_points_coords.assert_called_once_with(1)
        viewer.highlight_curve.assert_called_once_with("1", [1, 0.5, 0, 1])

        args, _ = viewer.set_hud_text.call_args
        texte_affiche = args[0]
        self.assertIn("Courbe 1", texte_affiche)
        self.assertIn("(0.00, 0.00, 0.00)", texte_affiche)
        self.assertIn("(1.00, 1.00, 1.00)", texte_affiche)

        self.assertEqual(viewer._default_last_hovered, "1")

    def test_default_on_hover_change_curve(self):
        viewer = self._make_viewer_with_mocks()
        viewer._default_last_hovered = "1"

        viewer.model.get_end_points_coords.return_value = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]

        viewer._default_on_hover("3")

        viewer.highlight_curve.assert_any_call("1", [1, 1, 1, 1])
        viewer.highlight_curve.assert_any_call("3", [1, 0.5, 0, 1])
        self.assertEqual(viewer._default_last_hovered, "3")

class TestViewerBezierInteractions(unittest.TestCase):
    """Tests for Bezier curve modification interactions via the Viewer."""

    def _make_viewer_with_mocks(self):
        """Creates a Viewer with all necessary mocks."""
        from bot.viewer.viewer import Viewer
        viewer = Viewer()

        # Mock connection and HUD text display
        viewer._conn = MagicMock()
        viewer.set_hud_text = MagicMock()

        # Mock the model
        viewer.model = MagicMock()

        return viewer


    @patch('bot.viewer.viewer.BezierCurve')
    def test_bezier_conversion_success(self, MockBezierCurve):
        """Verifies the conversion of a classic curve into a Bezier curve."""
        viewer = self._make_viewer_with_mocks()

        # State preparation
        viewer._default_last_hovered = "42"
        degree = 3
        coords_a = [0.0, 0.0, 0.0]
        coords_b = [10.0, 0.0, 0.0]
        viewer.model.get_end_points_coords.return_value = [coords_a, coords_b]

        # Mock configuration for the static method _default_control_points
        MockBezierCurve._default_control_points.return_value = [coords_a, [3.3, 0, 0], [6.6, 0, 0], coords_b]

        # Configuration of the mocked instance returned by BezierCurve(...)
        mock_curve_instance = MagicMock()
        MockBezierCurve.return_value = mock_curve_instance

        # Method call
        viewer.bezier_conversion(degree)

        # Assertions
        viewer.model.get_end_points_coords.assert_called_once_with(42)
        MockBezierCurve._default_control_points.assert_called_once_with(coords_a, coords_b, degree)
        MockBezierCurve.assert_called_once_with("42", MockBezierCurve._default_control_points.return_value, degree)
        viewer.model.set_curve.assert_called_once_with("42", mock_curve_instance)

    def test_bezier_conversion_no_selection(self):
        """Verifies behavior if no curve is selected/hovered."""
        viewer = self._make_viewer_with_mocks()
        viewer._default_last_hovered = None  # No selection

        viewer.bezier_conversion(3)

        # Verification of the HUD error
        viewer.set_hud_text.assert_called_once_with("Impossible to convert: no curve selected")
        # Verifies the model was not called
        viewer.model.get_end_points_coords.assert_not_called()

    def test_bezier_conversion_no_model(self):
        """Verifies behavior if a curve is selected but no model is connected."""
        viewer = self._make_viewer_with_mocks()
        viewer._default_last_hovered = "42"
        viewer.model = None  # No model

        viewer.bezier_conversion(3)

        # Verification of the HUD error
        viewer.set_hud_text.assert_called_once_with("Impossible to convert: no model loaded")


    def test_move_control_point_success(self):
        """Verifies that the modification of a control point is correctly transmitted to the model."""
        viewer = self._make_viewer_with_mocks()

        tag = 42
        cp_index = 1
        new_pos = [5.0, 10.0, 0.0]

        viewer.move_control_point(tag, cp_index, new_pos)

        # Verifies the model is updated
        viewer.model.update_control_point.assert_called_once_with(tag, cp_index, new_pos)
        # Verifies the success message in the HUD
        viewer.set_hud_text.assert_called_once_with(f"Point de contrôle {cp_index} de la courbe {tag} déplacé.")

    def test_move_control_point_no_model(self):
        """Verifies behavior if attempting to move a point without a connected model."""
        viewer = self._make_viewer_with_mocks()
        viewer.model = None  # No model

        viewer.move_control_point(42, 1, [0, 0, 0])

        # Verification of the HUD error
        viewer.set_hud_text.assert_called_once_with("Aucun modèle chargé.")


class TestViewerCurveEditMode(unittest.TestCase):

    def _make_viewer(self):
        from bot.viewer.viewer import Viewer
        viewer = Viewer()
        viewer._conn = MagicMock()
        return viewer

    def test_set_edit_mode_sends_command(self):
        viewer = self._make_viewer()
        viewer.set_edit_mode(True, 7)
        viewer._conn.send.assert_called_with(('set_edit_mode', {'enabled': True, 'curve_tag': 7}))

    def test_set_active_curve_sends_command(self):
        viewer = self._make_viewer()
        viewer.set_active_curve(9)
        viewer._conn.send.assert_called_with(('set_active_curve', {'curve_tag': 9}))

    def test_default_on_curve_selected_enables_edit_mode(self):
        viewer = self._make_viewer()
        viewer.set_edit_mode = MagicMock()
        viewer.set_active_curve = MagicMock()
        viewer.set_hud_text = MagicMock()

        viewer._default_on_curve_selected("5")

        viewer.set_edit_mode.assert_called_once_with(True, 5)
        viewer.set_active_curve.assert_called_once_with(5)
        viewer.set_hud_text.assert_called_once()

    def test_default_on_cp_pick_end_commits_to_model(self):
        viewer = self._make_viewer()
        viewer.model = MagicMock()

        viewer._default_on_cp_pick_end({'tag': '4', 'cp_index': 2, 'world_pos': [1.0, 2.0, 3.0]})

        viewer.model.update_control_point.assert_called_once_with(4, 2, [1.0, 2.0, 3.0])

if __name__ == '__main__':
    unittest.main()
