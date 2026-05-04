"""
System tests — Viewer subprocess lifecycle.

These tests start the REAL Viewer subprocess (Panda3D included) and verify the
IPC layer: the process starts, receives commands over the pipe and shuts down
cleanly.  A display is required; the suite is skipped automatically in headless
environments.

Note: these tests will briefly open a Panda3D window.
"""

import sys
import time
import unittest

import pytest


def _has_display() -> bool:
    """Return True if a graphical display is available."""
    if sys.platform == "darwin":
        return True  # macOS always has a display
    import os

    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.mark.skipif(not _has_display(), reason="no display available")
class TestViewerSubprocessLifecycle(unittest.TestCase):
    """Start and stop the real Panda3D subprocess."""

    def _start_viewer(self, model=None):
        from bot.viewer.viewer import Viewer

        v = Viewer()
        if model:
            v.connect(model)
        v.run()
        return v

    def test_run_starts_a_live_process(self):
        v = self._start_viewer()
        try:
            self.assertIsNotNone(v._process)
            # Give the subprocess a moment to initialise
            time.sleep(1.0)
            self.assertTrue(v._process.is_alive())
        finally:
            v.stop()

    def test_stop_terminates_the_process(self):
        v = self._start_viewer()
        time.sleep(1.0)
        v.stop()
        # After stop(), the process reference is cleared
        self.assertIsNone(v._process)

    def test_stop_closes_the_connection(self):
        v = self._start_viewer()
        time.sleep(1.0)
        v.stop()
        self.assertIsNone(v._conn)

    def test_stop_deregisters_observer(self):
        from bot.core.cad import Model as CADModel

        model = CADModel()
        model.open("data/profil_1.geo")
        try:
            v = self._start_viewer(model)
            time.sleep(1.0)
            v.stop()
            self.assertNotIn(v, model._observers)
        finally:
            model.finalize()

    def test_run_returns_self_for_chaining(self):
        from bot.viewer.viewer import Viewer

        v = Viewer()
        result = v.run()
        try:
            self.assertIs(result, v)
        finally:
            v.stop()


@pytest.mark.skipif(not _has_display(), reason="no display available")
class TestViewerIPCWithModel(unittest.TestCase):
    """
    Load a .geo file, connect a real Viewer and verify the model mutation
    path reaches the subprocess pipe without errors.
    """

    def setUp(self):
        from bot.core.cad import Model as CADModel
        from bot.viewer.viewer import Viewer

        self.model = CADModel()
        self.model.open("data/profil_1.geo")
        self.viewer = Viewer()
        self.viewer.connect(self.model).run()
        time.sleep(1.5)  # let the subprocess initialise and process the 'load'

    def tearDown(self):
        self.viewer.stop()
        self.model.finalize()

    def test_subprocess_is_alive_after_load(self):
        self.assertTrue(self.viewer._process.is_alive())

    def test_model_mutation_does_not_crash_subprocess(self):
        """Add a point and verify the subprocess is still alive afterwards."""
        self.model.add_point([200.0, 200.0, 0.0])
        time.sleep(0.5)  # let the update command be processed
        self.assertTrue(self.viewer._process.is_alive())

    def test_multiple_mutations_keep_subprocess_alive(self):
        for i in range(5):
            self.model.add_point([float(i * 10), 0.0, 0.0])
        time.sleep(0.5)
        self.assertTrue(self.viewer._process.is_alive())


if __name__ == "__main__":
    unittest.main()
