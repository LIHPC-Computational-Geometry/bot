"""Unit tests for the KISS shortcut SequenceBuffer, domain scope, and gestures."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from bot.control.shortcuts.binding import Drag, Key, Seq
from bot.control.shortcuts.engine import (
    Delta,
    Entry,
    GestureTracker,
    InputContext,
    SequenceBuffer,
    ShortcutRegistry,
)
from bot.viewer.contracts import ViewEventType


class TestSequenceBuffer(unittest.TestCase):
    def setUp(self):
        self.buf = SequenceBuffer()
        self.calls = []

        def seq_handler(ctx):
            self.calls.append("gg")

        def key_g(ctx):
            self.calls.append("g")

        def key_x(ctx):
            self.calls.append("x")

        self.seq_entry = Entry(Seq("g", "g", timeout=0.4), seq_handler, "local")
        self.key_g = Entry(Key("g"), key_g, "local")
        self.key_x = Entry(Key("x"), key_x, "local")
        self.buf.configure([self.seq_entry], [self.key_g, self.key_x])

    def test_seq_exact_match(self):
        self.assertIsNone(self.buf.push("g", now=1.0))
        entry = self.buf.push("g", now=1.1)
        self.assertIs(entry, self.seq_entry)

    def test_seq_prefix_wait(self):
        self.assertIsNone(self.buf.push("g", now=1.0))
        self.assertEqual(self.buf._buf, ["g"])

    def test_seq_timeout_reset(self):
        self.assertIsNone(self.buf.push("g", now=1.0))
        # After timeout, buffer clears then treats next key fresh.
        entry = self.buf.push("x", now=2.0)
        self.assertIs(entry, self.key_x)

    def test_seq_no_false_prefix(self):
        self.assertIsNone(self.buf.push("g", now=1.0))
        entry = self.buf.push("x", now=1.1)
        self.assertIs(entry, self.key_x)
        self.assertNotIn("gg", self.calls)

    def test_single_key_when_not_prefix(self):
        entry = self.buf.push("x", now=1.0)
        self.assertIs(entry, self.key_x)


class TestDomainScope(unittest.TestCase):
    def test_domain_scope_emits_event(self):
        events = []
        reg = ShortcutRegistry()

        @reg.bind(Key("n"), scope="domain")
        def new_point(ctx):
            return {"action": "new_point"}

        ctx = InputContext(
            base=MagicMock(),
            scene=None,
            mouse_handler=MagicMock(),
            on_event_cb=lambda et, data: events.append((et, data)),
        )
        reg._ctx = ctx
        entry = reg.entries()[0]
        reg._invoke(entry)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], ViewEventType.SHORTCUT)
        self.assertEqual(events[0][1]["action"], "new_point")

    def test_domain_scope_default_action_name(self):
        events = []
        reg = ShortcutRegistry()

        @reg.bind(Key("m"), scope="domain")
        def my_action(ctx):
            return None

        ctx = InputContext(
            base=MagicMock(),
            scene=None,
            mouse_handler=MagicMock(),
            on_event_cb=lambda et, data: events.append((et, data)),
        )
        reg._ctx = ctx
        reg._invoke(reg.entries()[0])
        self.assertEqual(events[0][1]["action"], "my_action")


class TestGestureTracker(unittest.TestCase):
    def test_drag_blocked_during_cp_drag(self):
        invoked = []
        tracker = GestureTracker()

        def pan(ctx, delta):
            invoked.append(delta)

        entry = Entry(Drag("left"), pan, "local")
        tracker.configure([entry], [], lambda e, *a: invoked.append((e, a)))

        tracker.on_frame(
            left_down=True,
            pos=(0.0, 0.0),
            modifiers=frozenset(),
            blocked=False,
        )
        tracker.on_frame(
            left_down=True,
            pos=(0.1, 0.0),
            modifiers=frozenset(),
            blocked=True,  # CP drag active
        )
        self.assertEqual(invoked, [])
        self.assertEqual(tracker._state, tracker._IDLE)

    def test_drag_fires_when_not_blocked(self):
        invoked = []
        tracker = GestureTracker()

        def pan(ctx, delta):
            pass

        entry = Entry(Drag("left"), pan, "local")

        def invoke(e, *args):
            invoked.append(args)

        tracker.configure([entry], [], invoke)
        tracker.on_frame(
            left_down=True, pos=(0.0, 0.0), modifiers=frozenset(), blocked=False
        )
        tracker.on_frame(
            left_down=True, pos=(0.05, 0.0), modifiers=frozenset(), blocked=False
        )
        self.assertEqual(len(invoked), 1)
        self.assertIsInstance(invoked[0][0], Delta)


if __name__ == "__main__":
    unittest.main()
