"""Unit tests for CompositeViewable registry routing."""

import unittest
from unittest.mock import MagicMock

from bot.viewer.tags import encode, CAD_NS, SPLINE_NS
from bot.viewer.contracts import ViewerCommandType, ViewEventType
from bot.viewer.viewable import CompositeViewable


class TestCompositeRegistry(unittest.TestCase):
    def setUp(self):
        self.cad = MagicMock()
        self.spline = MagicMock()
        self.cad.handle_event.return_value = [
            {"cmd": ViewerCommandType.UPDATE_HUD, "text": "cad"}
        ]
        self.spline.handle_event.return_value = [
            {"cmd": ViewerCommandType.UPDATE_HUD, "text": SPLINE_NS}
        ]
        self.composite = CompositeViewable({CAD_NS: self.cad, SPLINE_NS: self.spline})

    def test_routes_cad_tag(self):
        tag = encode(CAD_NS, 3)
        self.composite.handle_event(
            {"event_type": ViewEventType.CP_PICK_END, "tag": tag}
        )
        self.cad.handle_event.assert_called_once()
        self.spline.handle_event.assert_not_called()

    def test_routes_spline_tag(self):
        tag = encode(SPLINE_NS, "curve-uuid")
        self.composite.handle_event(
            {"event_type": ViewEventType.CP_PICK_END, "tag": tag}
        )
        self.spline.handle_event.assert_called_once()
        self.cad.handle_event.assert_not_called()

    def test_unknown_namespace_dropped(self):
        result = self.composite.handle_event(
            {"event_type": ViewEventType.CP_PICK_END, "tag": "unknown:1"}
        )
        self.assertEqual(result, [])
        self.cad.handle_event.assert_not_called()
        self.spline.handle_event.assert_not_called()

    def test_hover_without_namespace_falls_back_to_cad(self):
        self.composite.handle_event({"event_type": ViewEventType.HOVER, "tag": None})
        self.cad.handle_event.assert_called_once()


if __name__ == "__main__":
    unittest.main()
