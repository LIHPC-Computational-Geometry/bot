"""IPC data contracts between the parent (math) and child (render) processes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired  # type: ignore[attr-defined]

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


class ViewEvent(TypedDict, total=False):
    """Upstream user-interaction event from the child process."""

    event_type: str
    tag: str
    curve_tag: str
    cp_index: int
    world_pos: list[float]


class ViewerCommand(TypedDict, total=False):
    """Downstream command produced by adapters for the Viewer to dispatch."""

    cmd: str
    tag: str
    color: list[float]
    text: str
    enabled: bool
    curve_tag: str | int | None
    mask: int
