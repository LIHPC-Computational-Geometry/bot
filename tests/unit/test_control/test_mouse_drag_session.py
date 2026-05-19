import unittest
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
try:
    from bot.control.mouse import MouseHandler
    from bot.math.constraints import ConstraintManager
    from panda3d.core import Point2

    _HAS_PANDA_DEPS = True
except ModuleNotFoundError:
    MouseHandler = None
    _HAS_PANDA_DEPS = False


class _FakeScene:
    """A fake scene for testing mouse interactions without Panda3D rendering."""
    def __init__(self):
        self.hidden = False
        self.curves = {}
        self.cp_color_calls = []

    def set_cp_color(self, tag, cp_index, color):
        """Records calls to change control point colors."""
        self.cp_color_calls.append((tag, cp_index, color))

    def hide_axis_guide(self):
        """Hides the axis guide."""
        self.hidden = True

    def show_axis_guide(self, point, mask):
        """Called by _start_cp_drag."""
        self.axis_guide_shown = True

    def preview_control_point(self, curve_tag, cp_index, world_pos):
        """Called by _update_cp_drag."""
        self.previewed_cp = (curve_tag, cp_index, world_pos)

    def update_axis_guide(self, world_pos, mask):
        """Called by _update_cp_drag."""
        pass


class _FakeBase:
    """A fake Panda3D ShowBase for testing without the full engine."""
    def __init__(self):
        self._scene = _FakeScene()
        self.events = []
        self.mouseWatcherNode = MagicMock()
        self.messenger = MagicMock()

        self.render = MagicMock()
        self.cam = MagicMock()

        # Ensure a real vector is returned if Panda3D is installed
        # (essential because the C++ Plane() object does not accept Python mocks)
        try:
            from panda3d.core import Vec3

            self.render.getRelativeVector.return_value = Vec3(0, 1, 0)
        except ImportError:
            pass

    def _on_event_cb(self, event_type, data):
        """Records events emitted by the system."""
        self.events.append((event_type, data))


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestMouseDragSession(unittest.TestCase):
    """Test suite for the mouse drag session in MouseHandler."""

    def _make_handler(self):
        """Creates a pre-configured MouseHandler for testing drag sessions."""
        handler = MouseHandler.__new__(MouseHandler)
        handler.base = _FakeBase()
        handler.constraints = ConstraintManager(handler.base)
        handler.picker = MagicMock()

        # Set attributes for the drag session state
        handler.dragging_cp = True
        handler.drag_curve_tag = "1"
        handler.drag_cp_index = 2
        handler.drag_last_valid_world_pos = [4.0, 5.0, 6.0]
        handler.drag_offset = [0.0, 0.0, 0.0]
        handler._left_was_down = True
        handler.edit_mode_enabled = True

        # Set attributes on the constraint manager
        handler.constraints.axis_constraint_mask = 7
        handler.constraints.drag_plane = object()
        handler.constraints.drag_start_world_pos = [1.0, 2.0, 3.0]
        handler.constraints.drag_active_mask = 7
        return handler

    def test_finalize_drag_uses_last_valid_position_fallback(self):
        """Tests that ending a drag without a valid hit falls back to the last valid position."""
        handler = self._make_handler()
        handler.constraints.mouse_to_constrained_axis = lambda _m_pos: None

        handler._handle_cp_interaction(None, left_down=False)

        self.assertFalse(handler.dragging_cp)
        self.assertEqual(len(handler.base.events), 1)
        event_type, payload = handler.base.events[0]
        self.assertEqual(event_type, "cp_pick_end")
        self.assertEqual(payload["world_pos"], [4.0, 5.0, 6.0])
        self.assertTrue(handler.base._scene.hidden)

    def test_finalize_drag_resets_internal_state(self):
        """Tests that ending a drag correctly resets all drag-related internal variables."""
        handler = self._make_handler()
        handler.constraints.mouse_to_constrained_axis = lambda _m_pos: [7.0, 8.0, 9.0]

        handler._handle_cp_interaction(None, left_down=False)

        self.assertIsNone(handler.drag_curve_tag)
        self.assertIsNone(handler.drag_cp_index)
        self.assertIsNone(handler.drag_last_valid_world_pos)
        self.assertIsNone(handler.constraints.drag_plane)
        self.assertIsNone(handler.constraints.drag_start_world_pos)

    def test_drag_offset_is_preserved_during_update(self):
        """Verifies that if the user clicks near the center of the point, this offset is preserved during movement."""
        handler = self._make_handler()

        # The real center of our Control Point is at (10, 10, 0)
        metadata = {
            "curve_tag": "1",
            "cp_index": 2,
            "pick_kind": "cp",
            "point": [10.0, 10.0, 0.0],
        }

        # Step 1: The user clicks. The projection says their mouse points to (12, 10, 0).
        # They therefore clicked slightly next to the point.
        handler.constraints.mouse_to_constrained_axis = MagicMock(
            return_value=[12.0, 10.0, 0.0]
        )
        handler._start_cp_drag(metadata, Point2(0, 0))

        # The calculated offset must be Center(10, 10, 0) - Hit(12, 10, 0) = [-2.0, 0.0, 0.0]
        self.assertEqual(handler.drag_offset, [-2.0, 0.0, 0.0])
        self.assertTrue(handler.dragging_cp)

        # Step 2: The mouse moves. The new point targeted by the mouse is (15, 10, 0)
        handler.constraints.mouse_to_constrained_axis.return_value = [15.0, 10.0, 0.0]
        handler._update_cp_drag(Point2(1, 1))

        # The CP must be placed at: New Target Point(15, 10, 0) + Offset(-2, 0, 0) = (13, 10, 0)
        self.assertEqual(handler.drag_last_valid_world_pos, [13.0, 10.0, 0.0])

        # Verify that the final event transmits the correct coordinates
        event_type, payload = handler.base.events[-1]
        self.assertEqual(event_type, "cp_drag")
        self.assertEqual(payload["world_pos"], [13.0, 10.0, 0.0])

    def test_update_loss_of_mouse_focus_aborts_drag(self):
        """Verifies that the mouse losing focus (leaving the screen) aborts and properly closes the drag-and-drop session."""
        handler = self._make_handler()

        # Simulate that focus is lost
        handler.base.mouseWatcherNode.hasMouse.return_value = False
        task_mock = MagicMock()

        # Call the update function (as the game loop would)
        handler.update(task_mock)

        # The drag must stop
        self.assertFalse(handler.dragging_cp)

        # Verify that the end event is sent with the default mock position (4, 5, 6)
        event_type, payload = handler.base.events[-1]
        self.assertEqual(event_type, "cp_pick_end")
        self.assertEqual(payload["world_pos"], [4.0, 5.0, 6.0])

    def test_wheel_zoom_during_drag_does_not_break_session(self):
        """Verifies that triggering a system event (like zooming) does not corrupt the drag state."""
        handler = self._make_handler()

        # State is initially set to "dragging_cp = True" by _make_handler()
        self.assertTrue(handler.dragging_cp)

        # Simulate the mouse wheel command sent to the system
        handler.base.messenger.send("cmd_zoom", [1.1])

        # The action must not interrupt the drag and metadata must remain intact
        self.assertTrue(handler.dragging_cp)
        self.assertEqual(handler.drag_curve_tag, "1")
        self.assertEqual(handler.drag_cp_index, 2)


if __name__ == "__main__":
    unittest.main()
