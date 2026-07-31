from __future__ import annotations

import logging

from bot.core.spline import BEZIER_TYP, NURBS_TYP, SplineModel
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
    pack_curve_delta,
)
from bot.viewer.tags import (
    SPLINE_NS,
    decode,
    encode,
    is_namespaced,
)

_logger = logging.getLogger(__name__)


class SplineAdapter(BaseAdapter):
    """
    Adapter bridging a SplineModel to the Viewer IPC layer.
    Handles discretization of splines and control point interactions.
    """

    _SAMPLE_COUNT = 100
    curve_type_name: str = "spline"

    def __init__(self, model: SplineModel) -> None:
        super().__init__()
        self.color = [0.0, 0.5, 1.0, 1.0]
        self._model = model
        self._model.add_observer(self)

        # Route table mapping event types to specific handler methods
        self._event_handlers = {
            ViewEventType.HOVER: self._on_hover_event,
            ViewEventType.CURVE_SELECTED: self._on_curve_selected_event,
            ViewEventType.CP_PICK_END: self._on_cp_pick_end_event,
            ViewEventType.CREATE_SPLINE: self._on_shortcut_event,
        }

    # =========================================================================
    # PUBLIC API & CORE INTERFACES
    # =========================================================================

    def get_delta_load(self) -> ScenePayload:
        """Build the initial add payload with all spline curves."""
        return {
            "op": SceneUpdateOp.ADD,
            "changed_curves": self._build_all_spline_curves(),
        }

    def update(self, _model: SplineModel) -> None:
        """Observer callback: push an update delta when the model changes."""
        if self._update_callback is not None:
            self._update_callback(
                {
                    "op": SceneUpdateOp.UPDATE,
                    "changed_curves": self._build_all_spline_curves(),
                }
            )

    def handle_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Dispatch events using a dictionary of registered callbacks."""
        handler = self._event_handlers.get(event.get("event_type"))
        if handler:
            return handler(event)
        return []

    # =========================================================================fo
    # EVENT HANDLERS (ROUTED VIA DICTIONARY)
    # =========================================================================

    def _on_hover_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Extract tag and trigger hover visualization."""
        tag = event.get("tag") or event.get("curve_tag")
        return self._handle_hover(str(tag) if tag is not None else None)

    def _on_shortcut_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Process domain-specific shortcuts like creating a new interpolated spline."""
        points = event.get("points")
        if points and len(points) >= 2:
            try:
                self._model.add_interpolated_curve(points, len(points) - 1)
            except Exception() as exc:
                _logger.warning(
                    "SplineAdapter failed to create interpolated curve: %s", exc
                )
        return []

    def _on_curve_selected_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Activate edit mode for the selected spline."""
        local_id = self._resolve_spline_tag(event)
        if local_id is not None:
            return self._handle_curve_selected(encode(SPLINE_NS, local_id))
        return []

    def _on_cp_pick_end_event(self, event: ViewEvent) -> list[ViewerCommand]:
        """Apply the new control point position to the model."""
        local_id = self._resolve_spline_tag(event)
        if local_id is not None:
            return self._handle_cp_pick_end(event, local_id)
        return []

    # =========================================================================
    # MODEL MUTATIONS & ACTIONS
    # =========================================================================

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

    # =========================================================================
    # GEOMETRY & RENDERING BUILDERS
    # =========================================================================

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

    # =========================================================================
    # UTILITIES & HELPERS
    # =========================================================================

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
