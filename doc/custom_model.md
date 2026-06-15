# Connecting a New Model

The `Viewer` is decoupled from concrete business classes using an Anti-Corruption Layer (ACL) pattern. To connect a new data model, you must wrap it in an adapter class that adheres to the `IViewable` protocol.

## The IViewable Protocol

Every adapter must implement the following 4 methods:
1. `bind_update(callback)`: Registers a callback that triggers whenever the underlying model is modified.
2. `unbind_update()`: Clears the registered callback.
3. `get_delta_load()`: Packs the entire initial state of the model into an `ADD` operation payload.
4. `handle_event(event)`: Translates inbound `ViewEvent` user actions into a list of executable `ViewerCommand` payloads.

## Step-by-Step Implementation Example

Let's write a fully compliant adapter for a hypothetical custom polygonal model component (`CustomPolylineModel`).

### 1. Build the Adapter Class

```python
import logging
from bot.viewer.viewable import IViewable
from bot.viewer.contracts import ScenePayload, SceneUpdateOp, ViewEventType, ViewerCommandType, ViewerCommand, ViewEvent
from bot.viewer.serialize import pack_curve_delta
from bot.viewer.tags import encode, decode, is_namespaced

_logger = logging.getLogger(__name__)

class CustomPolylineAdapter(IViewable):
    NAMESPACE = "polyline"

    def __init__(self, model):
        self._model = model
        self._update_callback = None
        self._last_hovered = None
        # Connect to your model's observer pattern
        self._model.add_observer(self)

    def bind_update(self, callback):
        self._update_callback = callback

    def unbind_update(self):
        self._update_callback = None

    def get_delta_load(self):
        """Constructs the initial full scene payload."""
        return {
            "op": SceneUpdateOp.ADD,
            "changed_curves": self._build_render_deltas(),
            "bounds": {
                "min": [-10, -10, -10],
                "max": [10, 10, 10],
                "center": [0, 0, 0],
                "size": [20, 20, 20]
            }
        }

    def handle_event(self, event):
        """Processes user clicks or selections on this specific model namespace."""
        commands = []
        event_type = event.get("event_type")
        tag = event.get("curve_tag") or event.get("tag")

        # Validate that the tag belongs to this adapter's namespace
        if tag and is_namespaced(str(tag)):
            ns, local_id = decode(str(tag))
            if ns != self.NAMESPACE:
                return []
        else:
            return []

        if event_type == ViewEventType.CURVE_SELECTED:
            commands.append({
                "cmd": ViewerCommandType.UPDATE_HUD,
                "text": f"Selected Polyline Local ID: {local_id}"
            })
            commands.append({
                "cmd": ViewerCommandType.HIGHLIGHT_CURVE,
                "tag": str(tag),
                "color": [0, 0.8, 1, 1]  # Highlight blue
            })
        return commands

    def update(self, model):
        """Triggered automatically when the domain model emits a change notice."""
        if self._update_callback is not None:
            payload = {
                "op": SceneUpdateOp.UPDATE,
                "changed_curves": self._build_render_deltas()
            }
            self._update_callback(payload)

    def _build_render_deltas(self):
        """Converts internal raw coordinates to flat float32 byte payloads."""
        deltas = {}
        for item_id, polyline in self._model.get_all_items().items():
            # Generate a namespaced tag boundary (e.g., 'polyline:1')
            ns_tag = encode(self.NAMESPACE, item_id)

            # pack_curve_delta converts vertex arrays to structural bytes
            deltas[ns_tag] = pack_curve_delta(
                curve_points=polyline.vertices,  # list of [x, y, z]
                edges=polyline.edges,            # list of (idx_a, idx_b)
                curve_type="linear"
            )
        return deltas
```

### 2. Connect and Execute
To initialize and bind your new adapter configuration directly via the Viewer:


```python
from bot.viewer.viewer import Viewer
# Assuming your models exist:
my_model = CustomPolylineModel()

viewer = Viewer()
# Inject the custom adapter into the private interface adapter slot
viewer._connect(CustomPolylineAdapter(my_model))
viewer.run()
```

