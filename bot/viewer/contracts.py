"""IPC data contracts between the parent (math) and child (render) processes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict, Union
from typing import NotRequired

from bot.core.spline import BEZIER_TYP, NURBS_TYP


class CurveGeometry(TypedDict):
    """Binary geometry channels for a single curve."""

    curve_vertices: bytes
    control_vertices: NotRequired[bytes]


class CurveDelta(TypedDict):
    """Per-curve render delta sent over the IPC pipe."""

    type: Literal["linear", BEZIER_TYP, NURBS_TYP]
    geometry: CurveGeometry
    vertex_count: int
    edges: list[tuple[int, int]] | None

    degree: NotRequired[int]
    cp_count: NotRequired[int]


class ScenePayload(TypedDict):
    """Universal exchange format for incremental scene updates."""

    op: Literal["add", "update", "delete"]
    changed_curves: dict[str, CurveDelta]
    deleted_curves: NotRequired[list[str]]
    bounds: NotRequired[dict[str, Any]]
    points: NotRequired[bytes]
    edges: NotRequired[list[tuple[int, int, str]]]


class EventHover(TypedDict):
    event_type: Literal["hover"]
    tag: str | None

class EventCurveSelected(TypedDict):
    event_type: Literal["curve_selected"]
    curve_tag: str

class EventCPInteraction(TypedDict):
    event_type: Literal["cp_pick_start", "cp_drag", "cp_pick_end"]
    curve_tag: str
    cp_index: int
    world_pos: list[float]

class EventPick(TypedDict):
    event_type: Literal["pick"]
    world_pos: list[float]

ViewEvent = Union[EventHover, EventCurveSelected, EventCPInteraction, EventPick]



class CmdHighlightCurve(TypedDict):
    cmd: Literal["highlight_curve"]
    tag: str
    color: list[float]

class CmdUpdateHud(TypedDict):
    cmd: Literal["update_hud"]
    text: str

class CmdSetEditMode(TypedDict):
    cmd: Literal["set_edit_mode"]
    enabled: bool
    curve_tag: str | None

class CmdSetActiveCurve(TypedDict):
    cmd: Literal["set_active_curve"]
    curve_tag: str | None

ViewerCommand = Union[
    CmdHighlightCurve, CmdUpdateHud, CmdSetEditMode, CmdSetActiveCurve
]