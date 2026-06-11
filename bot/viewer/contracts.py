"""IPC data contracts between the parent (math) and child (render) processes."""

from __future__ import annotations

from typing import Any, Literal, TypedDict, Union, NotRequired
from enum import Enum

from bot.core.spline import BEZIER_TYP, NURBS_TYP


class SceneUpdateOp(str, Enum):
    """
    Category 1: Geometric Update Flow (Parent -> Child)
    Heavy payloads used to synchronize 3D topology and geometry.
    """
    ADD = "add"          # Initializes or fully rebuilds the scene.
    UPDATE = "update"    # Applies a partial patch to existing geometries.
    DELETE = "delete"    # Removes one or multiple geometries from the scene.


class ViewerCommandType(str, Enum):
    """
    Category 2: Display State Commands (Parent -> Child)
    Orders given to the GUI by the parent process.
    """
    # FIXME Color changes on hover should be detected and applied locally by the child.
    HIGHLIGHT_CURVE = "highlight_curve"

    # Legitimate: The parent sends domain-specific data (calculated by the kernel) that the child lacks.
    UPDATE_HUD = "update_hud"

    # Legitimate: The parent (script/kernel) forces the UI into edit mode programmatically.
    SET_EDIT_MODE = "set_edit_mode"

    # Legitimate: The parent targets a specific curve programmatically.
    SET_ACTIVE_CURVE = "set_active_curve"

    # FIXME The child already has the math logic (ConstraintManager) to calculate axes locally.
    SET_AXIS_CONSTRAINT = "set_axis_constraint"

    # Legitimate: The parent commands the child process to terminate gracefully.
    EXIT = "exit"


class ViewEventType(str, Enum):
    """
    Category 3: User Interaction Events (Child -> Parent)
    Notifications of physical user actions occurring in the 3D window.
    """
    # FIXME If no custom user callback is set, sending this just to trigger a HIGHLIGHT_CURVE is wasteful.
    HOVER = "hover"

    # Legitimate: The parent needs to know which curve was clicked to update its internal state.
    CURVE_SELECTED = "curve_selected"

    # Legitimate: Notifies the parent that a control point drag operation has started.
    CP_PICK_START = "cp_pick_start"

    # FIXME Sending mouse position at 60 FPS clogs the IPC pipe.
    # The child should handle real-time visual updates locally via `preview_evaluate`.
    CP_DRAG = "cp_drag"

    # Legitimate (Crucial): The parent receives the final position to permanently update the math kernel.
    CP_PICK_END = "cp_pick_end"

    # Legitimate: The parent receives an absolute 3D coordinate to instantiate a new free point.
    PICK = "pick"


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