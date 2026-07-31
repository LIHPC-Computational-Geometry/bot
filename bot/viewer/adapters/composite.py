from __future__ import annotations

import logging
from collections.abc import Callable

from bot.core.cad import CADModel
from bot.core.spline import SplineModel
from bot.viewer.contracts import (
    ScenePayload,
    ViewerCommand,
    ViewEvent,
    ViewEventType,
)
from bot.viewer.serialize import (
    merge_deltas,
)
from bot.viewer.tags import (
    CAD_NS,
    is_namespaced,
    prefix,
)

from . import Adapter
from .adapter_cad import CADAdapter
from .adapter_spline import SplineAdapter

_logger = logging.getLogger(__name__)

class CompositeAdapter:
    """
    Aggregator for multiple Adapter adapters (e.g., CAD and Spline).
    It routes events to the correct adapter based on tag namespaces.
    """

    def __init__(self, adapters: dict[str, Adapter]) -> None:
        self._adapters = adapters
        self._update_callback: Callable[[ScenePayload], None] | None = None

        # Define global event types that should be broadcasted to all adapters
        self.GLOBAL_EVENT_TYPES = {
            ViewEventType.HOVER,
            ViewEventType.SHORTCUT,
            ViewEventType.CREATE_SPLINE,
        }

    @classmethod
    def from_models(
        cls, cad_model: CADModel, spline_model: SplineModel | None = None
    ) -> CompositeAdapter:
        """Construct a composite adapter from CAD and optional spline models."""
        adapters: dict[str, Adapter] = {"cad": CADAdapter(cad_model)}
        if spline_model is not None:
            adapters["spline"] = SplineAdapter(spline_model)
        return cls(adapters)

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        """Fan in update callbacks from all child adapters."""
        self._update_callback = callback

        def _fan_in(payload: ScenePayload) -> None:
            if self._update_callback is not None:
                self._update_callback(payload)

        for adapter in self._adapters.values():
            adapter.bind_update(_fan_in)

    def unbind_update(self) -> None:
        """Clear the update callback on this composite and all adapters."""
        self._update_callback = None
        for adapter in self._adapters.values():
            adapter.unbind_update()

    def get_delta_load(self) -> ScenePayload:
        """Merge initial-load payloads from all adapters."""
        payloads = [adapter.get_delta_load() for adapter in self._adapters.values()]
        return merge_deltas(*payloads)

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Route an event to the adapter matching the tag namespace."""
        tag = event.get("curve_tag") or event.get("tag")
        event_type = event.get("event_type", "")

        # NOTE: Broadcast global events to all registered adapters
        if tag is None and event_type in self.GLOBAL_EVENT_TYPES:
            commands = []
            for adapter in self._adapters.values():
                commands.extend(adapter.handle_event(event))
            return commands

        # NOTE: Route namespaced events to their specific adapter (e.g., 'spline:123')
        if tag is not None and is_namespaced(str(tag)):
            ns = prefix(str(tag))
            if ns is not None:
                adapter = self._adapters.get(ns)
                if adapter is not None:
                    return adapter.handle_event(event)
            return []

        # NOTE: Fallback: Route to the default CAD adapter if no namespace is provied
        cad = self._adapters.get(CAD_NS)
        if cad is not None:
            return cad.handle_event(event)
        return []
