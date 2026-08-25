# Viewer API and Anti-Corruption Layer (`bot.viewer`)

The `bot.viewer` module serves as the vital bridge between the mathematical core (`bot.core`) and the 3D rendering engine (`bot.view`). It manages the lifecycle of the 3D subprocess, handles high-performance Inter-Process Communication (IPC), and implements an Anti-Corruption Layer (ACL) through adapters to ensure the domain models remain fully decoupled from the UI.

---

## 1. The Main Entry Point: `Viewer`

Located in `bot/viewer/viewer.py`.

The `Viewer` class is the primary public API for developers using the **BOT** package in an interactive session (like IPython). Its main responsibility is to spawn and manage the Panda3D renderer in a completely separate background process, ensuring the main Python REPL remains non-blocking and interactive.

### Key Methods
*   `connect_models(cad_model, spline_model=None)`: Binds your mathematical models to the viewer using a `CompositeAdapter` under the hood.
*   `run()`: Spawns the Panda3D subprocess and starts the event-listening daemon thread.
*   `stop()`: Cleanly shuts down the subprocess and frees the multiprocessing pipes.
*   `add_callback(event_type: ViewEventType, callback)`: Allows you to inject custom Python functions that trigger when the user interacts with the 3D canvas (e.g., clicking a curve).
*   **Visual Commands**: Methods like `highlight_curve()`, `set_hud_text()`, and `set_edit_mode()` send imperative commands directly to the child process to update the display.

---

## 2. IPC Data Contracts

Located in `bot/viewer/contracts.py`.

Because the math models and the 3D viewer live in two different processes, they must communicate via a `multiprocessing.Pipe`. To ensure type safety and clarity, all messages are strictly categorized into three `IntEnum` classes:

1.  **`SceneUpdateOp` (Parent -> Child)**: Heavy payloads used to synchronize 3D topology and geometry.
    *   `ADD`: Initializes or fully rebuilds the scene.
    *   `UPDATE`: Applies a partial binary patch to existing geometries.
    *   `DELETE`: Removes geometries from the scene.
2.  **`ViewerCommandType` (Parent -> Child)**: Orders given to the Graphical User Interface (e.g., `HIGHLIGHT_CURVE`, `UPDATE_HUD`, `SET_ACTIVE_CURVE`).
3.  **`ViewEventType` (Child -> Parent)**: Notifications of physical user actions occurring in the 3D window (e.g., `HOVER`, `CURVE_SELECTED`, `CP_PICK_START`, `CP_DRAG`, `CP_PICK_END`).

---

## 3. The Anti-Corruption Layer: Adapters

Located in `bot/viewer/adapters/`.

The Viewer does not read data directly from `CADModel` or `SplineModel`. Instead, it relies on Adapters. Adapters listen to the `Observable` events from the core models and translate the complex mathematical data into a standardized `ScenePayload` dict.

*   **`CADAdapter`**: Discretizes OpenCASCADE/gmsh curves into linear segments. Handles interactions like adding free points.
*   **`SplineAdapter`**: Evaluates Bézier and NURBS curves into renderable polylines and extracts control points/knots for the 3D edit mode.
*   **`CompositeAdapter`**: Aggregates multiple adapters. It acts as a router, examining the namespace of a tag (e.g., `"cad:42"` vs. `"spline:curve-1"`) to forward user events to the correct specific adapter.

---

## 4. Binary Serialization for Performance

Located in `bot/viewer/serialize.py`.

Sending thousands of 3D coordinates between processes using standard Python lists or JSON would cause massive lag. To maintain 60 FPS, especially during real-time control point dragging, the `bot.viewer.serialize` module packs geometry into contiguous float32 byte arrays.

### Key Helpers
*   `floats_to_bytes()`: Converts a sequence of `[x, y, z]` triples into a flat `numpy.float32` byte array.
*   `pack_curve_delta()`: Builds a `CurveDelta` dictionary containing the binary geometry channels (`curve_vertices`, `cp_vertices`, `knots`, `weights`), the vertex counts, and the topological edge connectivity.