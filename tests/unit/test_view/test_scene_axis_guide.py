import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
try:
    from bot.view.scene import Scene
    _HAS_PANDA_DEPS = True
except ModuleNotFoundError:
    Scene = None
    _HAS_PANDA_DEPS = False


class _FakeChildren:
    def detach(self):
        return None


class _FakeGuideNode:
    def __init__(self):
        self.hidden = True

    def getChildren(self):
        return _FakeChildren()

    def hide(self):
        self.hidden = True

    def show(self):
        self.hidden = False

    def attachNewNode(self, _):
        return self

    def removeNode(self):
        return None


@unittest.skipUnless(_HAS_PANDA_DEPS, "Panda3D runtime dependencies not installed")
class TestSceneAxisGuide(unittest.TestCase):
    def _make_scene(self):
        scene = Scene.__new__(Scene)
        scene.axis_constraint_mask = 7
        scene._constraint_guide_np = _FakeGuideNode()
        scene._transform_gizmo_np = _FakeGuideNode()
        scene._constraint_guide_origin = None
        scene._constraint_guide_visible = False
        scene._drawn_axes = []
        scene._guide_length = lambda: 10.0

        def _record_axis(_root, _origin, axis, _length):
            scene._drawn_axes.append(axis)

        scene._draw_axis_line = _record_axis
        return scene

    def test_mask_four_draws_only_z(self):
        scene = self._make_scene()
        scene.update_axis_guide([0, 0, 0], 4)
        self.assertEqual(scene._drawn_axes, ["z", "z"])

    def test_mask_three_draws_x_and_y(self):
        scene = self._make_scene()
        scene.update_axis_guide([0, 0, 0], 3)
        self.assertEqual(scene._drawn_axes, ["x", "y", "x", "y"])

    def test_show_hide_updates_visibility(self):
        scene = self._make_scene()
        scene.show_axis_guide([1, 2, 3], 1)
        self.assertFalse(scene._constraint_guide_np.hidden)
        self.assertFalse(scene._transform_gizmo_np.hidden)
        scene.hide_axis_guide()
        self.assertTrue(scene._constraint_guide_np.hidden)
        self.assertTrue(scene._transform_gizmo_np.hidden)


if __name__ == "__main__":
    unittest.main()
