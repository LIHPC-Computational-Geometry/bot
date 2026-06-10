"""Unit tests for CADAdapter Anti-Corruption Layer."""

import unittest
from unittest.mock import MagicMock, patch

from bot.viewer.tags import encode, CAD_NS
from bot.viewer.viewable import CADAdapter


class TestCADAdapterACL(unittest.TestCase):
    def setUp(self):
        self.model = MagicMock()
        self.model.bounds = {"min": [0, 0, 0], "max": [1, 1, 1]}
        self.model.has_curve.return_value = True
        self.adapter = CADAdapter(self.model)

    def test_drop_malformed_tag_on_curve_selected(self):
        commands = self.adapter.handle_event(
            {"event_type": "curve_selected", "tag": "not-namespaced"}
        )
        self.assertEqual(commands, [])

    def test_drop_unknown_cad_curve(self):
        self.model.has_curve.return_value = False
        tag = encode(CAD_NS, 999)
        commands = self.adapter.handle_event(
            {"event_type": "curve_selected", "tag": tag, "curve_tag": tag}
        )
        self.assertEqual(commands, [])

    def test_valid_tag_routes_curve_selected(self):
        tag = encode(CAD_NS, 5)
        commands = self.adapter.handle_event(
            {"event_type": "curve_selected", "tag": tag, "curve_tag": tag}
        )
        self.assertTrue(any(c.get("cmd") == "set_edit_mode" for c in commands))
        self.assertTrue(
            any(
                c.get("curve_tag") == tag
                for c in commands
                if c.get("cmd") == "set_edit_mode"
            )
        )

    @patch.object(CADAdapter, "_build_changed_curves", return_value={})
    def test_update_emits_op_update(self, _mock_build):
        callback = MagicMock()
        self.adapter.bind_update(callback)
        self.adapter.update(self.model)
        payload = callback.call_args[0][0]
        self.assertEqual(payload["op"], "update")
        self.assertIn("changed_curves", payload)

    @patch.object(CADAdapter, "_build_changed_curves", return_value={})
    def test_get_delta_load_emits_op_add(self, _mock_build):
        payload = self.adapter.get_delta_load()
        self.assertEqual(payload["op"], "add")


if __name__ == "__main__":
    unittest.main()
