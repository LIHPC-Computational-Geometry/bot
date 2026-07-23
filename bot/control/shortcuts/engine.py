"""Shortcut registry, sequence buffer, and gesture tracker."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from bot.control.shortcuts.binding import (
    Binding,
    Click,
    Drag,
    Hold,
    Key,
    Seq,
    Wheel,
)
from bot.viewer.contracts import ViewEventType

Scope = Literal["local", "domain"]
Handler = Callable[..., Any]

_BUTTON_MAP = {
    "left": 0,
    "middle": 1,
    "right": 2,
}
_BUTTON_FROM_INDEX = {v: k for k, v in _BUTTON_MAP.items()}

# Movement squared threshold (Panda3D normalised coords) to distinguish click vs drag.
_DRAG_THRESHOLD_SQ = 1e-6


@dataclass
class Entry:
    binding: Binding
    fn: Handler
    scope: Scope


@dataclass
class InputContext:
    """Runtime context passed to every shortcut handler."""

    base: Any
    scene: Any | None
    mouse_handler: Any
    on_event_cb: Callable[[ViewEventType, Any], None]
    camera_controller: Any | None = None

    @property
    def messenger(self):
        return self.base.messenger


@dataclass
class Delta:
    """Screen-space mouse delta for continuous drag handlers."""

    x: float
    y: float


class SequenceBuffer:
    """
    Buffer for key sequences and single keys.

    Exact ``Seq`` match → return that entry.
    Buffer is a prefix of some ``Seq`` → wait (return None).
    Otherwise → try a single-key ``Key`` match for the last key.
    """

    def __init__(self) -> None:
        self._buf: list[str] = []
        self._last_t: float = 0.0
        self._timeout: float = 0.4
        self._seq_entries: list[Entry] = []
        self._key_entries: dict[str, Entry] = {}

    def configure(self, seq_entries: list[Entry], key_entries: list[Entry]) -> None:
        self._seq_entries = list(seq_entries)
        self._key_entries = {
            e.binding.name: e for e in key_entries if isinstance(e.binding, Key)
        }
        timeouts = [
            e.binding.timeout for e in seq_entries if isinstance(e.binding, Seq)
        ]
        self._timeout = max(timeouts) if timeouts else 0.4

    def clear(self) -> None:
        self._buf.clear()

    def _is_prefix(self, candidate: tuple[str, ...]) -> bool:
        for entry in self._seq_entries:
            keys = entry.binding.keys
            if len(candidate) < len(keys) and keys[: len(candidate)] == candidate:
                return True
        return False

    def _matching_timeout(self, candidate: tuple[str, ...]) -> float:
        timeouts = []
        for entry in self._seq_entries:
            keys = entry.binding.keys
            if len(candidate) < len(keys) and keys[: len(candidate)] == candidate:
                timeouts.append(entry.binding.timeout)
        return max(timeouts) if timeouts else self._timeout

    def push(self, key: str, now: float | None = None) -> Entry | None:
        t = time.monotonic() if now is None else now
        if self._buf and (t - self._last_t) > self._timeout:
            self._buf.clear()

        self._buf.append(key)
        self._last_t = t
        candidate = tuple(self._buf)

        for entry in self._seq_entries:
            if entry.binding.keys == candidate:
                self._buf.clear()
                return entry

        if self._is_prefix(candidate):
            self._timeout = self._matching_timeout(candidate)
            return None

        self._buf.clear()
        return self._key_entries.get(key)


class GestureTracker:
    """
    Minimal mouse gesture state machine: idle → pressed → dragging → released.

    Domain interactions (CP drag, curve pick) stay in ``MouseHandler`` and pass
    ``blocked=True`` so camera gestures do not fire.
    """

    _IDLE = 0
    _PRESSED = 1
    _DRAGGING = 2

    def __init__(self) -> None:
        self._state = self._IDLE
        self._button: str | None = None
        self._modifiers: frozenset[str] = frozenset()
        self._press_pos: tuple[float, float] | None = None
        self._prev_pos: tuple[float, float] | None = None
        self._drag_entries: list[Entry] = []
        self._click_entries: list[Entry] = []
        self._invoke: Callable[..., None] | None = None

    def configure(
        self,
        drag_entries: list[Entry],
        click_entries: list[Entry],
        invoke: Callable[..., None],
    ) -> None:
        self._drag_entries = list(drag_entries)
        self._click_entries = list(click_entries)
        self._invoke = invoke

    def reset(self) -> None:
        self._state = self._IDLE
        self._button = None
        self._modifiers = frozenset()
        self._press_pos = None
        self._prev_pos = None

    def _find(
        self, entries: list[Entry], button: str, modifiers: frozenset[str]
    ) -> Entry | None:
        for entry in entries:
            b = entry.binding
            if b.button == button and b.modifiers == modifiers:
                return entry
        return None

    def on_frame(
        self,
        *,
        left_down: bool,
        pos: tuple[float, float] | None,
        modifiers: frozenset[str],
        blocked: bool,
    ) -> None:
        if blocked or pos is None:
            if self._state != self._IDLE:
                self.reset()
            return

        button = "left"
        if left_down and self._state == self._IDLE:
            self._state = self._PRESSED
            self._button = button
            self._modifiers = frozenset(modifiers)
            self._press_pos = pos
            self._prev_pos = pos
            return

        if left_down and self._state in (self._PRESSED, self._DRAGGING):
            assert self._prev_pos is not None and self._press_pos is not None
            dx = pos[0] - self._prev_pos[0]
            dy = pos[1] - self._prev_pos[1]
            if self._state == self._PRESSED:
                pdx = pos[0] - self._press_pos[0]
                pdy = pos[1] - self._press_pos[1]
                if pdx * pdx + pdy * pdy > _DRAG_THRESHOLD_SQ:
                    self._state = self._DRAGGING
            if self._state == self._DRAGGING and (dx != 0.0 or dy != 0.0):
                entry = self._find(
                    self._drag_entries, self._button or button, self._modifiers
                )
                if entry is not None and self._invoke is not None:
                    self._invoke(entry, Delta(dx, dy))
            self._prev_pos = pos
            return

        if not left_down and self._state == self._PRESSED:
            entry = self._find(
                self._click_entries, self._button or button, self._modifiers
            )
            if entry is not None and self._invoke is not None:
                self._invoke(entry)
            self.reset()
            return

        if not left_down:
            self.reset()


class ShortcutRegistry:
    """Declarative registry: binding + handler + local/domain scope."""

    def __init__(self) -> None:
        self._entries: list[Entry] = []
        self._ctx: InputContext | None = None
        self.sequence_buffer = SequenceBuffer()
        self.gesture_tracker = GestureTracker()
        self._hold_keys: dict[str, int] = {}
        self._hold_entry: Entry | None = None
        self._installed = False

    def bind(self, binding: Binding, *, scope: Scope = "local"):
        def decorator(fn: Handler) -> Handler:
            self._entries.append(Entry(binding, fn, scope))
            return fn

        return decorator

    def entries(self) -> list[Entry]:
        return list(self._entries)

    def update_context(self, **kwargs: Any) -> None:
        if self._ctx is None:
            return
        for k, v in kwargs.items():
            setattr(self._ctx, k, v)

    def _invoke(self, entry: Entry, *args: Any) -> None:
        if self._ctx is None:
            return
        result = entry.fn(self._ctx, *args)
        if entry.scope == "domain":
            if isinstance(result, dict):
                payload = dict(result)
                payload.setdefault("action", entry.fn.__name__)
            else:
                payload = {"action": entry.fn.__name__}
            self._ctx.on_event_cb(ViewEventType.SHORTCUT, payload)

    def install(self, ctx: InputContext) -> None:
        """Wire bindings to Panda3D ``accept`` / tasks / gesture tracker."""
        self._ctx = ctx
        base = ctx.base

        key_entries = [e for e in self._entries if isinstance(e.binding, Key)]
        seq_entries = [e for e in self._entries if isinstance(e.binding, Seq)]
        wheel_entries = [e for e in self._entries if isinstance(e.binding, Wheel)]
        hold_entries = [e for e in self._entries if isinstance(e.binding, Hold)]
        drag_entries = [e for e in self._entries if isinstance(e.binding, Drag)]
        click_entries = [e for e in self._entries if isinstance(e.binding, Click)]

        self.sequence_buffer.configure(seq_entries, key_entries)
        self.gesture_tracker.configure(drag_entries, click_entries, self._invoke)

        # Collect all key names that participate in Key or Seq bindings.
        watched: set[str] = set()
        for e in key_entries:
            watched.add(e.binding.name)
        for e in seq_entries:
            watched.update(e.binding.keys)

        for name in watched:
            base.accept(name, self._on_key, [name])

        for e in wheel_entries:
            event = "wheel_up" if e.binding.direction == "up" else "wheel_down"

            def _wheel(entry=e):
                self._invoke(entry)

            base.accept(event, _wheel)

        if hold_entries:
            # Only one Hold binding is supported (arrow-pan style).
            self._hold_entry = hold_entries[0]
            self._hold_keys = {k: 0 for k in self._hold_entry.binding.keys}
            for key in self._hold_keys:
                base.accept(key, self._set_hold_key, [key, 1])
                base.accept(key + "-up", self._set_hold_key, [key, 0])
            base.taskMgr.add(self._hold_task, "ShortcutHoldTask")

        self._installed = True

    def _on_key(self, name: str) -> None:
        entry = self.sequence_buffer.push(name)
        if entry is not None:
            self._invoke(entry)

    def _set_hold_key(self, key: str, value: int) -> None:
        self._hold_keys[key] = value

    def _hold_task(self, task):
        if self._hold_entry is not None and self._ctx is not None:
            if any(self._hold_keys.values()):
                self._invoke(self._hold_entry, dict(self._hold_keys))
        return task.cont


# Module-level singleton used by ``@bind`` and ``shortcuts_registry``.
registry = ShortcutRegistry()


def bind(binding: Binding, *, scope: Scope = "local"):
    """Register a shortcut on the default registry."""
    return registry.bind(binding, scope=scope)
