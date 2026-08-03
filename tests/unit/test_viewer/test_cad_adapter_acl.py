"""Unit tests for CADAdapter Anti-Corruption Layer."""

import unittest
from unittest.mock import MagicMock

from bot.core.cad import CADModel
from bot.viewer.adapters.adapter_cad import CADAdapter
from bot.viewer.contracts import SceneUpdateOp, ViewerCommandType, ViewEventType
from bot.viewer.serialize import bytes_to_point_list
from bot.viewer.tags import CAD_NS, encode

GEO_FILE = "data/profil_1.geo"


class TestCADAdapterACLEventGuards(unittest.TestCase):
    """Tag validation and routing guards — isolated with a mock model."""

    def setUp(self):
        self.model = MagicMock()
        self.model.bounds = {"min": [0, 0, 0], "max": [1, 1, 1]}
        self.model.has_curve.return_value = True
        self.adapter = CADAdapter(self.model)

    def test_drop_malformed_tag_on_curve_selected(self):
        commands = self.adapter.handle_event(
            {"event_type": ViewEventType.CURVE_SELECTED, "tag": "not-namespaced"}
        )
        self.assertEqual(commands, [])

    def test_drop_unknown_cad_curve(self):
        self.model.has_curve.return_value = False
        tag = encode(CAD_NS, 999)
        commands = self.adapter.handle_event(
            {"event_type": ViewEventType.CURVE_SELECTED, "tag": tag, "curve_tag": tag}
        )
        self.assertEqual(commands, [])

    def test_valid_tag_routes_curve_selected(self):
        tag = encode(CAD_NS, 5)
        commands = self.adapter.handle_event(
            {"event_type": ViewEventType.CURVE_SELECTED, "tag": tag, "curve_tag": tag}
        )
        self.assertEqual(
            commands,
            [
                {
                    "cmd": ViewerCommandType.SET_EDIT_MODE,
                    "enabled": True,
                    "curve_tag": tag,
                },
                {"cmd": ViewerCommandType.SET_ACTIVE_CURVE, "curve_tag": tag},
                {
                    "cmd": ViewerCommandType.UPDATE_HUD,
                    "text": f"Editing curve {tag}: drag a control point.",
                },
            ],
        )


class TestCADAdapterACLWithModel(unittest.TestCase):
    """Delta load and observer update with a real CADModel."""

    def setUp(self):
        self.model = CADModel()
        self.model.open(GEO_FILE)
        self.adapter = CADAdapter(self.model)

    def tearDown(self):
        self.model.finalize()

    def test_get_delta_load_emits_op_add_with_curves(self):
        payload = self.adapter.get_delta_load()
        self.assertEqual(payload["op"], SceneUpdateOp.ADD)
        self.assertEqual(
            set(payload["changed_curves"].keys()),
            {encode(CAD_NS, tag) for tag in self.model.get_curve_tags()},
        )
        for delta in payload["changed_curves"].values():
            self.assertGreater(delta["vertex_count"], 0)
            pts = bytes_to_point_list(
                delta["geometry"]["curve_vertices"], delta["vertex_count"]
            )
            self.assertEqual(len(pts), delta["vertex_count"])

    def test_update_emits_op_update_with_changed_curves(self):
        callback = MagicMock()
        self.adapter.bind_update(callback)
        self.model.add_point([50.0, 50.0, 0.0])
        self.assertEqual(callback.call_count, 1)
        payload = callback.call_args[0][0]
        self.assertEqual(payload["op"], SceneUpdateOp.UPDATE)
        self.assertEqual(
            set(payload["changed_curves"].keys()),
            {encode(CAD_NS, tag) for tag in self.model.get_curve_tags()},
        )


if __name__ == "__main__":
    unittest.main()
