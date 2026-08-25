# Input and Control Management (`bot.control`)

The `bot.control` module is responsible for capturing, interpreting, and routing user hardware inputs (mouse and keyboard). It acts as the intermediary between the Panda3D rendering engine (`bot.view`) and the application logic, dispatching events either locally (for camera and UI updates) or globally (for mathematical model modifications).

---

## 1. Mouse Interaction and Raycasting

The mouse logic is divided into two primary components: state tracking and 3D picking.

### `MouseHandler` (`bot/control/mouse.py`)
The `MouseHandler` tracks the state of the mouse buttons and the cursor's position every frame. It acts as an orchestrator that decides what an input means based on the current context (e.g., hovering, dragging a control point, or drawing a new spline).

**Key Responsibilities:**
*   **Hover Detection**: Continuously checks what object is under the cursor and dispatches a `HOVER` event if it changes.
*   **Drag Sessions**: Manages the complex state machine for dragging control points (`CP_PICK_START`, `CP_DRAG`, `CP_PICK_END`). It calculates the 3D offset and projects the 2D screen coordinates into a constrained 3D axis.
*   **Gesture Forwarding**: Passes unhandled mouse movements to the `GestureTracker` (for camera panning) or the `CreateSplineTool` (when in drawing mode).

### `RayPicker` (`bot/control/picker.py`)
To translate a 2D mouse click into a 3D object selection, the project uses Raycasting.

**How it works:**
1.  A `CollisionRay` is shot from the camera lens through the 2D mouse coordinates into the 3D world.
2.  A `CollisionTraverser` tests this ray against all objects equipped with specific collision masks (`MASK_CURVE` and `MASK_CP`).
3.  The `pick_entry()` method sorts the collisions. It includes a priority system (`_get_priority_distance_depth()`) that intentionally favors selecting Control Points over Curves if both overlap, ensuring a smooth editing experience.

---

## 2. Camera Navigation: `CameraController`

Located in `bot/control/camera.py`.

The 3D environment uses an **Orthographic Camera**, which means there is no perspective distortion (parallel lines remain parallel). This is the standard for CAD and engineering software.

**Key Features:**
*   **Pivot-Based Rotation**: The camera does not rotate around itself. Instead, it is attached to a `focal_node` (the pivot). When the user rotates the view, they are rotating the pivot, ensuring the model always stays centered.
*   **Dynamic Clipping & Film Size**: The camera automatically recalculates its "film size" (zoom level) and its near/far clipping planes based on the spatial bounds of the loaded geometry. This prevents large models from disappearing (clipping).
*   **Smooth Animations**: Using Panda3D's `Interval` system (`posInterval`, `hprInterval`), the camera provides smooth transitions when recentering or aligning to standard planes (Top, Front, Right).

---

## 3. Interactive State Machines: `CreateSplineTool`

Located in `bot/control/create_tool.py`.

Creating geometry interactively requires tracking the user's progress across multiple clicks. The `CreateSplineTool` handles the B-Spline creation state machine.

**States:**
*   `IDLE`: The tool is inactive.
*   `WAITING_FIRST_POINT`: The user has activated the tool but hasn't clicked yet.
*   `DRAWING`: The user has placed at least one point. A dynamic rubber-band line evaluates a temporary spline to preview the curve to the user before they commit.

Once the user commits (e.g., by pressing Enter), the tool packages the coordinates and fires a `CREATE_SPLINE` event back to the domain model.

---

## 4. UI Overlays: `CursorManager`

Located in `bot/control/cursor_manager.py`.

The `CursorManager` manages the 2D visual cursor overlay and its visibility state within the active window. When specific interactive modes are enabled (such as drawing a new spline), the manager replaces the default OS cursor with a high-precision 2D vector crosshair anchored at the center of the viewport (`base.render2d`).

---

## 5. The Shortcut Engine

Located in `bot/control/shortcuts/` and `bot/control/shortcuts_registry.py`.

Instead of hardcoding key presses directly into the application loop, **BOT** uses a powerful declarative shortcut registry.

*   **`@bind` Decorator**: Developers can easily map physical inputs (like `Key("c")` or `Drag("left")`) to specific Python functions.
*   **Sequence & Gesture Buffers**: The engine (`engine.py`) maintains a sequence buffer to allow complex combinations (e.g., pressing "A" then "B") and a gesture tracker to distinguish a quick mouse click from a deliberate camera drag.
*   **Scopes**:
    *   `local`: Executes immediately in the visual child process.
    *   `domain`: Packages the command into a `ViewEventType.SHORTCUT` payload and sends it over the IPC pipe to the parent process.

For a detailed guide on adding your own inputs, refer to the [Custom Controls and Shortcuts Guide](../guides/custom-controls-and-shortcuts.md).