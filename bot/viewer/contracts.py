"""IPC data contracts between the parent (math) and child (render) processes."""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Literal, NotRequired, TypedDict, Union

from bot.core.spline import BEZIER_TYP, NURBS_TYP


class SceneUpdateOp(IntEnum):
    """
    Category 1: Geometric Update Flow (Parent -> Child)
    Heavy payloads used to synchronize 3D topology and geometry.
    """

    ADD = 1  # Initializes or fully rebuilds the scene.
    UPDATE = 2  # Applies a partial patch to existing geometries.
    DELETE = 3  # Removes one or multiple geometries from the scene.


class ViewerCommandType(IntEnum):
    """
    Category 2: Display State Commands (Parent -> Child)
    Orders given to the GUI by the parent process.
    """

    # FIXME Color changes on hover should be detected and applied locally by the child.
    HIGHLIGHT_CURVE = 10

    # Legitimate: The parent sends domain-specific data (calculated by the kernel) that the child lacks.
    UPDATE_HUD = 11

    # Legitimate: The parent (script/kernel) forces the UI into edit mode programmatically.
    SET_EDIT_MODE = 12

    # Legitimate: The parent targets a specific curve programmatically.
    SET_ACTIVE_CURVE = 13

    # FIXME The child already has the math logic (ConstraintManager) to calculate axes locally.
    SET_AXIS_CONSTRAINT = 14

    # Legitimate: The parent commands the child process to terminate gracefully.
    EXIT = 15

    RELOAD_CONFIG = 16


class ViewEventType(IntEnum):
    """
    Category 3: User Interaction Events (Child -> Parent)
    Notifications of physical user actions occurring in the 3D window.
    """

    # FIXME If no custom user callback is set, sending this just to trigger a HIGHLIGHT_CURVE is wasteful.
    HOVER = 100

    # Legitimate: The parent needs to know which curve was clicked to update its internal state.
    CURVE_SELECTED = 101

    # Legitimate: Notifies the parent that a control point drag operation has started.
    CP_PICK_START = 102

    # FIXME Sending mouse position at 60 FPS clogs the IPC pipe.
    # The child should handle real-time visual updates locally via `preview_evaluate`.
    CP_DRAG = 103

    # Legitimate (Crucial): The parent receives the final position to permanently update the math kernel.
    CP_PICK_END = 104

    # Legitimate: The parent receives an absolute 3D coordinate to instantiate a new free point.
    PICK = 105


ParentCommand = SceneUpdateOp | ViewerCommandType
ParentMessage = tuple[ParentCommand, Any]
ChildMessage = tuple[ViewEventType, Any]


class CurveGeometry(TypedDict):
    """Binary geometry channels for a single curve."""

    curve_vertices: bytes  # Flat float32 byte array of xyz coordinates for the evaluated curve points.
    cp_vertices: NotRequired[
        bytes
    ]  # Flat float32 byte array of xyz coordinates for the control points.
    knots: NotRequired[bytes]
    weights: NotRequired[bytes]


class CurveDelta(TypedDict):
    """Per-curve render delta sent over the IPC pipe."""

    type: Literal["linear", BEZIER_TYP, NURBS_TYP]  # Mathematical type of the curve.
    geometry: (
        CurveGeometry  # The binary vertex data for the curve and its control points.
    )
    vertex_count: int  # Number of 3D vertices encoded in `geometry["curve_vertices"]`.
    edges: (
        list[tuple[int, int]] | None
    )  # Point connectivity indices (idx_a, idx_b) to form line segments.

    degree: NotRequired[
        int
    ]  # Mathematical degree of the spline (e.g., 3 for cubic Bézier/NURBS).
    cp_count: NotRequired[
        int
    ]  # Number of 3D control points encoded in `geometry["cp_vertices"]`.
    knot_count: NotRequired[
        int
    ]  # Number of knot scalars encoded in `geometry["knots"]`.
    weight_count: NotRequired[
        int
    ]  # Number of weight scalars encoded in `geometry["weights"]`.


class ScenePayload(TypedDict):
    """Universal exchange format for incremental scene updates."""

    op: SceneUpdateOp  # The type of operation (ADD, UPDATE, or DELETE).
    changed_curves: dict[
        str, CurveDelta
    ]  # Mapping of namespaced curve tags (e.g., "cad:1") to their update delta.
    deleted_curves: NotRequired[
        list[str]
    ]  # List of namespaced tags for curves that should be removed.
    bounds: NotRequired[
        dict[str, Any]
    ]  # Global scene bounding box dimensions (min, max, center, size).
    points: NotRequired[
        bytes
    ]  # Flat float32 byte array of xyz coordinates for all CAD nodes (load-only).
    edges: NotRequired[
        list[tuple[int, int, str]]
    ]  # Flat list of all scene edges (idx_a, idx_b, tag) (load-only).


class EventHover(TypedDict):
    event_type: Literal[ViewEventType.HOVER]
    tag: str | None


class EventCurveSelected(TypedDict):
    event_type: Literal[ViewEventType.CURVE_SELECTED]
    curve_tag: str


class EventCPPickStart(TypedDict):
    event_type: Literal[ViewEventType.CP_PICK_START]
    curve_tag: str
    cp_index: int
    world_pos: list[float]


class EventCPDrag(TypedDict):
    event_type: Literal[ViewEventType.CP_DRAG]
    curve_tag: str
    cp_index: int
    world_pos: list[float]


class EventCPPickEnd(TypedDict):
    event_type: Literal[ViewEventType.CP_PICK_END]
    curve_tag: str
    cp_index: int
    world_pos: list[float]


class EventPick(TypedDict):
    event_type: Literal[ViewEventType.PICK]
    world_pos: list[float]


ViewEvent = Union[
    EventHover,
    EventCurveSelected,
    EventCPPickStart,
    EventCPDrag,
    EventCPPickEnd,
    EventPick,
]


class CmdHighlightCurve(TypedDict):
    cmd: Literal[ViewerCommandType.HIGHLIGHT_CURVE]
    tag: str
    color: list[float]


class CmdUpdateHud(TypedDict):
    cmd: Literal[ViewerCommandType.UPDATE_HUD]
    text: str


class CmdSetEditMode(TypedDict):
    cmd: Literal[ViewerCommandType.SET_EDIT_MODE]
    enabled: bool
    curve_tag: str | None


class CmdSetActiveCurve(TypedDict):
    cmd: Literal[ViewerCommandType.SET_ACTIVE_CURVE]
    curve_tag: str | None


class CmdSetAxisConstraint(TypedDict):
    cmd: Literal[ViewerCommandType.SET_AXIS_CONSTRAINT]
    mask: int


ViewerCommand = Union[
    CmdHighlightCurve,
    CmdUpdateHud,
    CmdSetEditMode,
    CmdSetActiveCurve,
    CmdSetAxisConstraint,
]
