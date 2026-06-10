"""IViewable adapters bridging core models to the viewer IPC layer."""

from __future__ import annotations

import logging
from typing import Callable, Protocol

from bot.core.cad import CADModel
from bot.core.spline import SplineModel
from bot.viewer.contracts import CurveDelta, ScenePayload, ViewerCommand, ViewEvent
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


class IViewable(Protocol):
    """Interface for objects that can be rendered and observed by the Viewer."""

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None: ...

    def unbind_update(self) -> None: ...

    def get_delta_load(self) -> ScenePayload: ...

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]: ...


class CADAdapter:
    """Anti-Corruption Layer between namespaced UI tags and gmsh CAD geometry."""

    def __init__(self, model: CADModel):
        self._model = model
        self._update_callback: Callable[[ScenePayload], None] | None = None
        self._last_hovered: str | None = None
        self._model.add_observer(self)

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        self._update_callback = callback

    def unbind_update(self) -> None:
        self._update_callback = None

    def get_delta_load(self) -> ScenePayload:
        changed_curves = self._build_changed_curves()
        flat_points, flat_edges = self._build_flat_topology(changed_curves)
        payload: ScenePayload = {
            "op": "add",
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
        event_type = event.get("event_type", "")
        tag = event.get("tag") or event.get("curve_tag")

        if event_type == "hover":
            return self._handle_hover(tag)
        if event_type == "curve_selected":
            if tag is None or self._resolve_cad_tag_str(str(tag)) is None:
                return []
            return self._handle_curve_selected(str(tag))
        if event_type == "pick" and event.get("world_pos") is not None:
            try:
                self._model.add_point(list(event["world_pos"]))
            except Exception as exc:
                _logger.warning("CAD pick add_point failed: %s", exc)
            return []
        if event_type == "cp_pick_end":
            return self._handle_cp_pick_end(event)
        return []

    def update(self, _model: CADModel) -> None:
        if self._update_callback is not None:
            self._update_callback(
                {
                    "op": "update",
                    "changed_curves": self._build_changed_curves(),
                }
            )

    def _resolve_cad_tag(self, event: ViewEvent) -> int | None:
        raw = event.get("curve_tag") or event.get("tag")
        if raw is None:
            return None
        return self._resolve_cad_tag_str(str(raw))

    def _resolve_cad_tag_str(self, tag_str: str) -> int | None:
        if not is_namespaced(tag_str):
            return None
        decoded = decode(tag_str)
        if decoded is None or decoded[0] != CAD_NS:
            return None
        local_id = parse_cad_local_id(tag_str)
        if local_id is None or not self._model.has_curve(local_id):
            return None
        return local_id

    def _build_changed_curves(self) -> dict[str, CurveDelta]:
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
        except Exception as exc:
            _logger.warning("CADAdapter failed to build curves: %s", exc)
        return changed

    def _build_flat_topology(
        self, changed_curves: dict[str, CurveDelta]
    ) -> tuple[list[list[float]], list[tuple[int, int, str]]]:
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

    def _handle_hover(self, tag: str | None) -> list[ViewerCommand]:
        commands: list[ViewerCommand] = []
        if tag:
            tag_str = str(tag)
            if self._last_hovered and self._last_hovered != tag_str:
                commands.append(
                    {
                        "cmd": "highlight_curve",
                        "tag": self._last_hovered,
                        "color": [1, 1, 1, 1],
                    }
                )

            info_text = f"--- Curve {tag_str} ---\n"
            local_id = self._resolve_cad_tag_str(tag_str)
            if local_id is not None:
                try:
                    coords_a, coords_b = self._model.get_end_points_coords(local_id)
                    pt_a = f"({coords_a[0]:.2f}, {coords_a[1]:.2f}, {coords_a[2]:.2f})"
                    pt_b = f"({coords_b[0]:.2f}, {coords_b[1]:.2f}, {coords_b[2]:.2f})"
                    info_text += "Type: linear segment\n"
                    info_text += f"Endpoint A: {pt_a}\n"
                    info_text += f"Endpoint B: {pt_b}"
                except Exception as exc:
                    info_text += f"Error: {exc}"
            else:
                info_text += "Type: unknown"

            commands.extend(
                [
                    {"cmd": "update_hud", "text": info_text},
                    {"cmd": "highlight_curve", "tag": tag_str, "color": [1, 0.5, 0, 1]},
                ]
            )
            self._last_hovered = tag_str
        else:
            if self._last_hovered:
                commands.append(
                    {
                        "cmd": "highlight_curve",
                        "tag": self._last_hovered,
                        "color": [1, 1, 1, 1],
                    }
                )
                commands.append(
                    {
                        "cmd": "update_hud",
                        "text": "Ready. Hover or click on curves.",
                    }
                )
                self._last_hovered = None
        return commands

    def _handle_curve_selected(self, tag: str) -> list[ViewerCommand]:
        return [
            {"cmd": "set_edit_mode", "enabled": True, "curve_tag": tag},
            {"cmd": "set_active_curve", "curve_tag": tag},
            {
                "cmd": "update_hud",
                "text": f"Editing curve {tag}: drag a control point.",
            },
        ]

    def _handle_cp_pick_end(self, event: ViewEvent) -> list[ViewerCommand]:
        # CAD linear segments do not support control-point editing in v1.
        self._resolve_cad_tag(event)
        return []


class SplineAdapter:
    """Anti-Corruption Layer for ferrispline-backed spline curves."""

    _SAMPLE_COUNT = 100

    def __init__(self, model: SplineModel):
        self._model = model
        self._update_callback: Callable[[ScenePayload], None] | None = None
        self._model.add_observer(self)

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        self._update_callback = callback

    def unbind_update(self) -> None:
        self._update_callback = None

    def get_delta_load(self) -> ScenePayload:
        return {
            "op": "add",
            "changed_curves": self._build_all_spline_curves(),
        }

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        event_type = event.get("event_type", "")
        local_id = self._resolve_spline_tag(event)
        if local_id is None:
            return []

        ns_tag = encode(SPLINE_NS, local_id)

        if event_type == "curve_selected":
            return self._handle_curve_selected(ns_tag)
        if event_type == "cp_pick_end":
            return self._handle_cp_pick_end(event, local_id)
        return []

    def update(self, _model: SplineModel) -> None:
        if self._update_callback is not None:
            self._update_callback(
                {
                    "op": "update",
                    "changed_curves": self._build_all_spline_curves(),
                }
            )

    def _resolve_spline_tag(self, event: ViewEvent) -> str | None:
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

    def _build_all_spline_curves(self) -> dict[str, CurveDelta]:
        curves: dict[str, CurveDelta] = {}
        for local_id in self._model.curves:
            delta = self._build_spline_curve(local_id)
            if delta is not None:
                curves[encode(SPLINE_NS, local_id)] = delta
        return curves

    def _build_spline_curve(self, local_id: str) -> CurveDelta | None:
        try:
            control_points = self._model.get_control_points(local_id)
            curve_points = self._model._evaluate(local_id, self._SAMPLE_COUNT)
            degree = self._model.get_degree(local_id)
            edges = [(i, i + 1) for i in range(len(curve_points) - 1)]
            return pack_curve_delta(
                curve_points,
                curve_type="bezier",
                control_points=control_points,
                degree=degree,
                edges=edges,
            )
        except Exception as exc:
            _logger.warning("SplineAdapter failed to build curve %s: %s", local_id, exc)
            return None

    def _handle_curve_selected(self, ns_tag: str) -> list[ViewerCommand]:
        return [
            {"cmd": "set_edit_mode", "enabled": True, "curve_tag": ns_tag},
            {"cmd": "set_active_curve", "curve_tag": ns_tag},
            {
                "cmd": "update_hud",
                "text": f"Editing spline {ns_tag}: drag a control point.",
            },
        ]

    def _handle_cp_pick_end(
        self, event: ViewEvent, local_id: str
    ) -> list[ViewerCommand]:
        cp_index = int(event.get("cp_index", -1))
        world_pos = event.get("world_pos")
        if world_pos is None:
            return []
        try:
            self._model.move_control_point(local_id, cp_index, world_pos)
        except Exception as exc:
            _logger.warning("Spline cp_pick_end failed: %s", exc)
        return []


class CompositeViewable:
    """Aggregates adapters and routes events by tag namespace prefix."""

    def __init__(self, adapters: dict[str, IViewable]):
        self._adapters = adapters
        self._update_callback: Callable[[ScenePayload], None] | None = None

    @classmethod
    def from_models(
        cls, cad_model: CADModel, spline_model: SplineModel | None = None
    ) -> CompositeViewable:
        adapters: dict[str, IViewable] = {"cad": CADAdapter(cad_model)}
        if spline_model is not None:
            adapters["spline"] = SplineAdapter(spline_model)
        return cls(adapters)

    def bind_update(self, callback: Callable[[ScenePayload], None]) -> None:
        self._update_callback = callback

        def _fan_in(payload: ScenePayload) -> None:
            if self._update_callback is not None:
                self._update_callback(payload)

        for adapter in self._adapters.values():
            adapter.bind_update(_fan_in)

    def unbind_update(self) -> None:
        self._update_callback = None
        for adapter in self._adapters.values():
            adapter.unbind_update()

    def get_delta_load(self) -> ScenePayload:
        payloads = [adapter.get_delta_load() for adapter in self._adapters.values()]
        return merge_deltas(*payloads)

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        tag = event.get("curve_tag") or event.get("tag")
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
