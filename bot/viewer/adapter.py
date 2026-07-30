"""
Adapters bridging core models to the viewer IPC layer.
Adapters translate domain models (CAD, splines) into ``ScenePayload`` deltas for the render subprocess
and turn ``ViewEvent`` interactions into ``ViewerCommand`` responses.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

from bot.core.cad import CADModel
from bot.core.spline import BEZIER_TYP, NURBS_TYP, SplineModel
from bot.viewer.contracts import (
    CurveDelta,
    ScenePayload,
    SceneUpdateOp,
    ViewerCommand,
    ViewerCommandType,
    ViewEvent,
    ViewEventType,
)
from bot.viewer.serialize import (
    bytes_to_point_list,
    flatten_points_to_bytes,
    merge_deltas,
    pack_curve_delta,
)
from bot.viewer.tags import (
    CAD_NS,
    SPLINE_NS,
    decode,
    encode,
    is_namespaced,
    parse_cad_local_id,
    prefix,
)

_logger = logging.getLogger(__name__)


class Adapter(Protocol):
    """Interface for objects that can be rendered and observed by the Viewer."""

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        """Register a callback invoked when the underlying model changes."""

    def unbind_update(self) -> None:
        """Clear the update callback."""

    def get_delta_load(self) -> ScenePayload:
        """Return the full scene payload used for initial load."""

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Translate a user interaction into viewer commands."""


class BaseAdapter:
    """
    Base class providing common event handling, state management,
    and update binding for viewer adapters.
    """

    curve_type_name: str = "curve"

    def __init__(self) -> None:
        self._update_callback: Callable[[ScenePayload], None] | None = None
        self._last_hovered: str | None = None
        self.color: list[float] = [1.0, 0.0, 1.0, 1.0]
        self.hover_color: list[float] = [1.0, 0.5, 0.0, 1.0]

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        """Register a callback invoked when the underlying model changes."""
        self._update_callback = callback

    def unbind_update(self) -> None:
        """Clear the update callback."""
        self._update_callback = None

    def _handle_hover(self, tag: str | None) -> list[ViewerCommand]:
        """Update HUD text and curve highlight on hover enter or leave."""
        commands: list[ViewerCommand] = []
        if tag:
            tag_str = str(tag)
            if self._last_hovered and self._last_hovered != tag_str:
                commands.append(
                    {
                        "cmd": ViewerCommandType.HIGHLIGHT_CURVE,
                        "tag": self._last_hovered,
                        "color": self.color,
                    }
                )
            info_text = f"--- Curve {tag_str} ---\n" + self._get_hover_info(tag_str)
            commands.extend(
                [
                    {"cmd": ViewerCommandType.UPDATE_HUD, "text": info_text},
                    {
                        "cmd": ViewerCommandType.HIGHLIGHT_CURVE,
                        "tag": tag_str,
                        "color": self.hover_color,
                    },
                ]
            )
            self._last_hovered = tag_str
        else:
            if self._last_hovered:
                commands.append(
                    {
                        "cmd": ViewerCommandType.HIGHLIGHT_CURVE,
                        "tag": self._last_hovered,
                        "color": self.color,
                    }
                )
                commands.append(
                    {
                        "cmd": ViewerCommandType.UPDATE_HUD,
                        "text": "Ready. Hover or click on curves.",
                    }
                )
                self._last_hovered = None
        return commands

    def _get_hover_info(self, tag_str: str) -> str:
        """
        Return model-specific curve information for HUD display.
        Should be overridden by subclasses.
        """
        return "Type: unknown"

    def _handle_curve_selected(self, tag: str) -> list[ViewerCommand]:
        """Enter edit mode for the selected curve."""
        return [
            {
                "cmd": ViewerCommandType.SET_EDIT_MODE,
                "enabled": True,
                "curve_tag": tag,
            },
            {"cmd": ViewerCommandType.SET_ACTIVE_CURVE, "curve_tag": tag},
            {
                "cmd": ViewerCommandType.UPDATE_HUD,
                "text": f"Editing {self.curve_type_name} {tag}: drag a control point.",
            },
        ]


class CADAdapter(BaseAdapter):
    """
    Adapter bridging a CADModel to the Viewer IPC layer.
    Converts CAD geometry into renderable deltas and handles CAD user interactions.
    """

    curve_type_name: str = "curve"

    def __init__(self, model: CADModel) -> None:
        super().__init__()
        self._model = model
        self._model.add_observer(self)

    def get_delta_load(self) -> ScenePayload:
        """Build the initial add payload with curves, bounds, and flat topology."""
        changed_curves = self._build_changed_curves()
        flat_points, flat_edges = self._build_flat_topology(changed_curves)
        payload: ScenePayload = {
            "op": SceneUpdateOp.ADD,
            "changed_curves": changed_curves,
            "bounds": dict(self._model.bounds),
        }
        if flat_points:
            payload["points"] = flatten_points_to_bytes(flat_points)
        if flat_edges:
            payload["edges"] = [
                (idx_a, idx_b, str(tag)) for idx_a, idx_b, tag in flat_edges
            ]
        return payload

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Dispatch hover, selection, pick, and control-point events."""
        event_type = event.get("event_type", "")
        tag = event.get("tag") or event.get("curve_tag")
        match event_type:
            case ViewEventType.HOVER:
                return self._handle_hover(tag)
            case ViewEventType.CURVE_SELECTED:
                if tag is None or self._resolve_cad_tag_str(str(tag)) is None:
                    return []
                return self._handle_curve_selected(str(tag))
            case ViewEventType.PICK:
                world_pos = event.get("world_pos")
                if world_pos is not None:
                    try:
                        self._model.add_point(list(world_pos))
                    except Exception() as exc:
                        _logger.warning("CAD pick add_point failed: %s", exc)
                return []
            case _:
                return []

    def update(self, _model: CADModel) -> None:
        """Observer callback: push an update delta when the model changes."""
        if self._update_callback is not None:
            self._update_callback(
                {
                    "op": SceneUpdateOp.UPDATE,
                    "changed_curves": self._build_changed_curves(),
                }
            )

    def _resolve_cad_tag(self, event: ViewEvent) -> int | None:
        """Extract and validate the CAD local curve id from an event."""
        raw = event.get("curve_tag") or event.get("tag")
        if raw is None:
            return None
        return self._resolve_cad_tag_str(str(raw))

    def _resolve_cad_tag_str(self, tag_str: str) -> int | None:
        """Return the CAD local id for a namespaced tag, or None if invalid."""
        if not is_namespaced(tag_str):
            return None
        decoded = decode(tag_str)
        if decoded is None or decoded[0] != CAD_NS:
            return None
        local_id = parse_cad_local_id(tag_str)
        if local_id is None or not self._model.has_curve(local_id):
            return None
        return local_id

    def _get_hover_info(self, tag_str: str) -> str:
        """Return CAD curve endpoint details for HUD display."""
        local_id = self._resolve_cad_tag_str(tag_str)
        if local_id is None:
            return "Type: unknown"
        try:
            coords_a, coords_b = self._model.get_end_points_coords(local_id)
            pt_a = f"({coords_a[0]:.2f}, {coords_a[1]:.2f}, {coords_a[2]:.2f})"
            pt_b = f"({coords_b[0]:.2f}, {coords_b[1]:.2f}, {coords_b[2]:.2f})"
            return f"Type: linear segment\nEndpoint A: {pt_a}\nEndpoint B: {pt_b}"
        except Exception() as exc:
            return f"Error: {exc}"

    def _build_changed_curves(self) -> dict[str, CurveDelta]:
        """Discretize all CAD curves into namespaced render deltas."""
        changed: dict[str, CurveDelta] = {}
        try:
            for gmsh_tag, (
                local_points,
                local_edges,
            ) in self._model.get_curve_discretization().items():
                ns_tag = encode(CAD_NS, gmsh_tag)
                changed[ns_tag] = pack_curve_delta(
                    local_points,
                    curve_type="linear",
                    edges=local_edges,
                )
        except Exception() as exc:
            _logger.warning("CADAdapter failed to build curves: %s", exc)
        return changed

    def _build_flat_topology(
        self, changed_curves: dict[str, CurveDelta]
    ) -> tuple[list[list[float]], list[tuple[int, int, str]]]:
        """Flatten per-curve geometry into a single point list and edge index."""
        flat_points: list[list[float]] = []
        flat_edges: list[tuple[int, int, str]] = []
        for tag, delta in changed_curves.items():
            pts = bytes_to_point_list(
                delta["geometry"]["curve_vertices"], delta["vertex_count"]
            )
            offset = len(flat_points)
            flat_points.extend(pts)
            edges = delta.get("edges") or [(i, i + 1) for i in range(len(pts) - 1)]
            for idx_a, idx_b in edges:
                flat_edges.append((offset + idx_a, offset + idx_b, str(tag)))
        return flat_points, flat_edges


class SplineAdapter(BaseAdapter):
    """
    Adapter bridging a SplineModel to the Viewer IPC layer.
    Handles discretization of splines and control point interactions.
    """

    _SAMPLE_COUNT = 100
    curve_type_name: str = "spline"

    def __init__(self, model: SplineModel) -> None:
        super().__init__()
        self.color = [0.0, 1.0, 1.0, 1.0]
        self._model = model
        self._model.add_observer(self)

    def get_delta_load(self) -> ScenePayload:
        """Build the initial add payload with all spline curves."""
        return {
            "op": SceneUpdateOp.ADD,
            "changed_curves": self._build_all_spline_curves(),
        }

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Dispatch selection and control-point drag events for spline curves."""
        event_type = event.get("event_type", "")
        tag = event.get("tag") or event.get("curve_tag")

        if event_type == ViewEventType.HOVER:
            tag_str = str(tag) if tag is not None else None
            return self._handle_hover(tag_str)

        local_id = self._resolve_spline_tag(event)
        if local_id is None:
            return []

        ns_tag = encode(SPLINE_NS, local_id)
        match event_type:
            case ViewEventType.CURVE_SELECTED:
                return self._handle_curve_selected(ns_tag)
            case ViewEventType.CP_PICK_END:
                return self._handle_cp_pick_end(event, local_id)
            case _:
                return []

    def update(self, _model: SplineModel) -> None:
        """Observer callback: push an update delta when the model changes."""
        if self._update_callback is not None:
            self._update_callback(
                {
                    "op": SceneUpdateOp.UPDATE,
                    "changed_curves": self._build_all_spline_curves(),
                }
            )

    def _resolve_spline_tag(self, event: ViewEvent) -> str | None:
        """Extract and validate the spline local curve id from an event."""
        raw = event.get("curve_tag") or event.get("tag")
        if raw is None:
            return None
        tag_str = str(raw)
        if not is_namespaced(tag_str):
            return None
        decoded = decode(tag_str)
        if decoded is None or decoded[0] != SPLINE_NS:
            return None
        local_id = decoded[1]
        if local_id not in self._model.curves:
            return None
        return local_id

    def _get_hover_info(self, tag_str: str) -> str:
        """Return spline curve details for HUD display."""
        decoded = decode(tag_str)
        if decoded is None:
            return "Type: unknown"
        namespace, local_id = decoded
        if local_id not in self._model.curves:
            return "Type: unknown"
        try:
            degree = self._model.get_degree(local_id)
            return f"Type: {namespace}\nDegree: {degree}"
        except Exception() as exc:
            return f"Error: {exc}"

    def _build_all_spline_curves(self) -> dict[str, CurveDelta]:
        """Build render deltas for every spline in the model."""
        curves: dict[str, CurveDelta] = {}
        for local_id in self._model.curves:
            delta = self._build_spline_curve(local_id)
            if delta is not None:
                curves[encode(SPLINE_NS, local_id)] = delta
        return curves

    def _build_spline_curve(self, local_id: str) -> CurveDelta | None:
        """Discretize one spline into a namespaced render delta."""
        try:
            control_points = self._model.get_control_points(local_id)
            degree = self._model.get_degree(local_id)
            knots = None
            curve_type = BEZIER_TYP
            weights = self._model.get_weights(local_id)
            curve_points = self._model._evaluate(local_id, self._SAMPLE_COUNT)
            edges = [(i, i + 1) for i in range(len(curve_points) - 1)]
            if self._model.curve_kind(local_id) == NURBS_TYP:
                knots = self._model.get_knots(local_id)
                curve_type = NURBS_TYP
            return pack_curve_delta(
                curve_points,
                curve_type=curve_type,
                control_points=control_points,
                degree=degree,
                knots=knots,
                weights=weights,
                edges=edges,
            )
        except Exception() as exc:
            _logger.warning("SplineAdapter failed to build curve %s: %s", local_id, exc)
            return None

    def _handle_cp_pick_end(
        self, event: ViewEvent, local_id: str
    ) -> list[ViewerCommand]:
        """Apply a control-point drag to the spline model."""
        cp_index = int(event.get("cp_index", -1))
        world_pos = event.get("world_pos")
        if world_pos is None:
            return []
        try:
            self._model.move_control_point(local_id, cp_index, world_pos)
        except Exception() as exc:
            _logger.warning("Spline cp_pick_end failed: %s", exc)
        return []


class CompositeAdapter:
    """
    Aggregator for multiple Adapter adapters (e.g., CAD and Spline).
    It routes events to the correct adapter based on tag namespaces.
    """

    def __init__(self, adapters: dict[str, Adapter]) -> None:
        self._adapters = adapters
        self._update_callback: Callable[[ScenePayload], None] | None = None

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

        if tag is None and event_type == ViewEventType.HOVER:
            commands = []
            for adapter in self._adapters.values():
                commands.extend(adapter.handle_event(event))
            return commands

        if tag is not None and is_namespaced(str(tag)):
            ns = prefix(str(tag))
            if ns is not None:
                adapter = self._adapters.get(ns)
                if adapter is not None:
                    return adapter.handle_event(event)
            return []

        cad = self._adapters.get(CAD_NS)
        if cad is not None:
            return cad.handle_event(event)
        return []
