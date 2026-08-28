# 3D Rendering Engine (`bot.view`)

The `bot.view` module is the visual heart of the **BOT** project. It runs entirely inside the child process and leverages the [Panda3D](https://www.panda3d.org/) game engine to render the geometric models in real-time.

This module is responsible for translating the mathematical geometry (received via IPC payloads) into visible pixels, handling lighting, and building collision volumes for user interaction.

---

## 1. The Application Core: `View`

Located in `bot/view/view.py`.

The `View` class inherits from Panda3D's `ShowBase`. It acts as the main application loop for the child process.

### Key Responsibilities
*   **Command Queue Processing**: Every frame, the `View` drains a thread-safe queue containing commands sent from the parent process (`SceneUpdateOp` and `ViewerCommandType`).
*   **Event Routing**: It initializes the input managers (`MouseHandler`, `CameraController`, `CursorManager`) and connects them to the global shortcut registry.
*   **Scene Delegation**: It passes geometry update payloads directly to the `Scene` object to be rendered.

---

## 2. Scene Management: `Scene`

Located in `bot/view/scene.py`.

The `Scene` class manages the overarching Panda3D environment graph. It does not handle the math; instead, it orchestrates the visual nodes.

### Key Responsibilities
*   **Geometry Construction**: Rebuilds the geometry tree from CAD data and instantiates `CurveApp` objects for each curve.
*   **Patching (`apply_patch`)**: Instead of rebuilding the entire scene every frame during an interaction (like dragging a point), it applies incremental binary geometry updates from the parent process to the specific curves.
*   **Lighting & Gizmos**: Sets up the default `AmbientLight` and `DirectionalLight`, and manages the `HUDGizmo` (the colored XYZ axis indicator in the corner).
*   **Axis Constraints Guides**: Displays the visual constraints (X, Y, Z lines) when the user is moving a control point on a constrained axis.

---

## 3. Visual and Physical Curves: `CurveApp`

Located in `bot/view/curve_app.py`.

A `CurveApp` represents a single 3D curve (whether it is a CAD segment or a B-Spline) in the viewer. It manages both how the curve looks and how it physically interacts with the mouse.

### Visual Rendering
*   **`__draw_curve()`**: Uses Panda3D's `LineSegs` to draw the main polyline connecting the evaluated curve points.
*   **`__draw_control_points()`**: Uses `GeomPoints` and `GeomVertexData` to render the interactive control points and the dashed lines connecting them.
*   **`__draw_knots()`**: Renders knot locations for NURBS curves.

### Physical Collisions
To allow the user to click on thin lines or small points in a 3D space, `CurveApp` builds collision solids.
*   **Curve Collisions**: Creates a `CollisionTube` around each segment of the curve.
*   **Control Point Collisions**: Creates a `CollisionSphere` around each control point.

These solids are grouped under `CollisionNode`s with specific bitmasks (`MASK_CURVE_PICK` and `MASK_CP_PICK`). This allows the `RayPicker` (in `bot.control`) to cast a ray from the camera and detect exactly what the user clicked.

---

## 4. Utilities (Never Used)

Located in `bot/view/utils.py`.

Contains helper classes for the view layer.
*   **`ColorGenerator`**: Generates visually distinct RGB colors using evenly spaced HSV hues, which is useful when assigning default colors to newly created splines.