import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
try:
    from bot.control.mouse import MouseHandler
    _HAS_PANDA_DEPS = True
except ModuleNotFoundError:
    MouseHandler = None
    _HAS_PANDA_DEPS = False


class _FakeScene:
    def __init__(self):
        self.hidden = False
        self.cp_color_calls = []

    def set_cp_color(self, tag, cp_index, color):
        self.cp_color_calls.append((tag, cp_index, color))

    def hide_axis_guide(self):
        self.hidden = True


class _FakeBase:
    def __init__(self):
        self._scene = _FakeScene()
        self.events = []

    def _on_event_cb(self, event_type, data):
        self.events.append((event_type, data))


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestMouseDragSession(unittest.TestCase):
    def _make_handler(self):
        handler = MouseHandler.__new__(MouseHandler)
        handler.base = _FakeBase()
        handler.axis_constraint_mask = 7
        handler.dragging_cp = True
        handler.drag_curve_tag = "1"
        handler.drag_cp_index = 2
        handler.drag_plane = object()
        handler.drag_start_world_pos = [1.0, 2.0, 3.0]
        handler.drag_last_valid_world_pos = [4.0, 5.0, 6.0]
        handler.drag_active_mask = 7
        handler._left_was_down = True
        return handler

    def test_finalize_drag_uses_last_valid_position_fallback(self):
        handler = self._make_handler()
        handler._mouse_to_constrained_axis = lambda _m_pos: None

        handler._handle_cp_interaction(None, left_down=False)

        self.assertFalse(handler.dragging_cp)
        self.assertEqual(len(handler.base.events), 1)
        event_type, payload = handler.base.events[0]
        self.assertEqual(event_type, "cp_pick_end")
        self.assertEqual(payload["world_pos"], [4.0, 5.0, 6.0])
        self.assertTrue(handler.base._scene.hidden)

    def test_finalize_drag_resets_internal_state(self):
        handler = self._make_handler()
        handler._mouse_to_constrained_axis = lambda _m_pos: [7.0, 8.0, 9.0]

        handler._handle_cp_interaction(None, left_down=False)

        self.assertIsNone(handler.drag_curve_tag)
        self.assertIsNone(handler.drag_cp_index)
        self.assertIsNone(handler.drag_plane)
        self.assertIsNone(handler.drag_start_world_pos)
        self.assertIsNone(handler.drag_last_valid_world_pos)


if __name__ == "__main__":
    unittest.main()
