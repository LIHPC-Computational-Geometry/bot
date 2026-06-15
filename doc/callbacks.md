# Customizing Callbacks

The `Viewer` provides an explicit mechanism to attach custom user routines directly to 3D interface interaction events. This enables user scripts to execute domain calculations instantly inside the main process when a user interacts with the canvas.

## How Callbacks Execute Under the Hood

When a user triggers an action in the 3D canvas, the data flows across the IPC tunnel. The background listener thread processes the incoming event using a **dual-stage execution policy**:

1. **User Callbacks (Interception Stage):** The listener thread checks if a customized hook is registered for this specific `ViewEventType`. If found, it executes it immediately, supplying the event metadata.
2. **Default Handlers (Visual State Stage):** Next, the system *always* hands the event over to `_default_event_handler`. This ensures standard automated behaviors (like real-time hovering highlights, canvas panning math, and text HUD changes) continue working seamlessly.

## API Usage

### Registering a Callback
Use `viewer.add_callback(event_type, callable)` to listen for specific actions.

```python
import bot
from bot.viewer.contracts import ViewEventType

# Initialize core model and viewer
cad_model = bot.CADModel()
viewer = bot.Viewer()
viewer.connect_models(cad_model)

# 1. Define your custom interaction function
def my_custom_pick_handler(event_data):
    # event_data contains strict structured dict payloads from the event type
    coordinates = event_data.get("world_pos")
    print(f"[REPL NOTICE] User clicked absolute space position: {coordinates}")

    # Example action: Modify the mathematical model live based on click location
    if coordinates:
        cad_model.add_point(coordinates)

# 2. Wire the handler to the PICK event action type
viewer.add_callback(ViewEventType.PICK, my_custom_pick_handler)

viewer.run()
```

## Unregistering a Callback
To clear out a previously set behavior and fall back purely on standard handling loops, use `remove_callback(event_type)`:

```python
viewer.remove_callback(ViewEventType.PICK)
```

## Key Interactive Event Reference

The following table details the most common events you can attach callbacks to:

| Event Type Enum (`ViewEventType`) | Payload Content Context | Common Use Case |
| :--- | :--- | :--- |
| `HOVER` | `{"tag": str \| None}` | Trigger external UI tooltips or database queries on elements. |
| `CURVE_SELECTED` | `{"curve_tag": str}` | Open property option cards or focus cameras on selection. |
| `CP_PICK_START` | `{"curve_tag": str, "cp_index": int, "world_pos": [...]}` | Freeze global history undo stacks or record structural pre-states. |
| `CP_PICK_END` | `{"curve_tag": str, "cp_index": int, "world_pos": [...]}` | Commit the finalized drag movement to the mathematical model kernel. |
| `PICK` | `{"world_pos": [x, y, z]}` | Instantiate new custom points, nodes, or primitives at absolute locations. |
