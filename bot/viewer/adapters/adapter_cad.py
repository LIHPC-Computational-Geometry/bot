from __future__ import annotations

import logging

from bot.core.cad import CADModel
from bot.viewer.adapters import BaseAdapter
from bot.viewer.contracts import (
    CurveDelta,
    ScenePayload,
    SceneUpdateOp,
    ViewerCommand,
    ViewEvent,
    ViewEventType,
)
from bot.viewer.serialize import (
    bytes_to_point_list,
    flatten_points_to_bytes,
    pack_curve_delta,
)
from bot.viewer.tags import (
    CAD_NS,
    decode,
    encode,
    is_namespaced,
    parse_cad_local_id,
)

_logger = logging.getLogger(__name__)

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

        self._event_handlers = {
            ViewEventType.HOVER: self._on_hover_event,
            ViewEventType.CURVE_SELECTED: self._on_curve_selected_event,
            ViewEventType.PICK: self._on_pick_event,
        }

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
        """Dispatch events using a dictionary of registered callbacks."""
        handler = self._event_handlers.get(event.get("event_type"))
        if handler:
            return handler(event)
        return []

    def _on_hover_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Extract tag and trigger hover visualization."""
        tag = event.get("tag") or event.get("curve_tag")
        return self._handle_hover(tag)

    def _on_curve_selected_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Activate edit mode for the selected CAD curve."""
        tag = event.get("tag") or event.get("curve_tag")
        if tag is None or self._resolve_cad_tag_str(str(tag)) is None:
            return []
        return self._handle_curve_selected(str(tag))

    def _on_pick_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Handle 3D point picking to add a new free point to the CAD model."""
        world_pos = event.get("world_pos")
        if world_pos is not None:
            try:
                self._model.add_point(list(world_pos))
            except Exception() as exc:
                _logger.warning("CAD pick add_point failed: %s", exc)
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