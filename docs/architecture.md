# Architecture and IPC Communication

To keep the Python REPL (e.g., IPython) fully interactive while maintaining a fluid 60 FPS 3D rendering pipeline, **bot** implements a split-process architecture. OpenGL and windowing contexts (Panda3D) run inside a dedicated subprocess, isolated from the mathematical calculations.

## Process Separation

1. **Parent Process (Main Process):**
   * Hosts your Python script or interactive REPL session.
   * Maintains the true mathematical models (`CADModel`, `SplineModel`).
   * Runs a background daemon thread to continuously listen for incoming data from the UI.
2. **Child Process (Subprocess):**
   * Runs the Panda3D application engine on its main thread (required for macOS/OpenGL stability).
   * Handles user input captures, camera matrices, and drawing loops.

```mermaid
flowchart TB
    subgraph Parent["Parent process"]
        REPL["IPython REPL"]
        EventThread["Existing daemon event thread"]
        Models["CADModel / SplineModel"]
        Adapters["CADAdapter / SplineAdapter ACL"]
        Composite["CompositeAdapter"]
        Viewer["Viewer"]
        REPL --> Models
        Models --> Adapters --> Composite --> Viewer
        EventThread -->|"handle_event"| Composite
    end

    subgraph Child["Child process — Panda3D"]
        App["View"]
        Scene["Scene.apply_patch"]
        Mouse["MouseHandler — drag unchanged"]
        Mouse --> App
        App --> Scene
    end

    Viewer -->|"add / update / delete"| App
    App -->|"ViewEvent incl. cp_drag / cp_pick_end"| EventThread
```

## Events vs. Commands

Communication across the IPC Pipe is strictly divided into two distinct paradigms based on direction and intent:

### 1. View Events (`ViewEventType`)
* **Direction:** Child Process -> Parent Process.
* **Intent:** Notification of a physical interaction performed by the user inside the 3D window (e.g., a mouse click, hovering over a curve, or releasing a dragged control point).
* **Data structure:** Serializable dictionaries carrying interaction metadata (e.g., `curve_tag`, `world_pos`, `cp_index`).

### 2. Viewer Commands (`ViewerCommandType` & `SceneUpdateOp`)
* **Direction:** Parent Process -> Child Process.
* **Intent:** Imperative instructions forcing the 3D window to update its state or render new frames.
* **Categories:**
  * **Topology Operations (`SceneUpdateOp`):** Heavyweight actions to synchronize 3D structures (`ADD`, `UPDATE`, `DELETE`).
  * **Display State Commands (`ViewerCommandType`):** Lightweight UI adjustments (`HIGHLIGHT_CURVE`, `UPDATE_HUD`, `SET_EDIT_MODE`).

### Comparative Summary

| Feature | View Event | Viewer Command |
| :--- | :--- | :--- |
| **Origin** | Subprocess User Inputs | Parent Math Kernel/Script |
| **Destination** | Background Listener Thread | 3D Engine Command Queue |
| **Philosophy** | "Something happened in the canvas" | "Change your pixels right now" |
| **Heavy Payloads** | No (metadata coordinates only) | Yes (contains float32 byte buffers for geometry) |

```mermaid
sequenceDiagram
    participant Kernel as Processus Parent (Noyau/Main)
    participant Pipe as Pipe Multiprocessing
    participant ViewerProc as Processus Enfant (Panda3D)
    participant Scene as bot.view.scene.Scene

    Note over Kernel, ViewerProc: Phase d'initialisation et d'envoi de scène
    Kernel->>Pipe: _send(SceneUpdateOp.ADD, ScenePayload)
    Pipe->>ViewerProc: conn.recv()
    ViewerProc->>Scene: _build_from_data(geom_data)

    Note over Kernel, ViewerProc: Interaction de l'utilisateur (Ex: Déplacement)
    Scene->>ViewerProc: on_event_cb(ViewEventType.CP_DRAG, data)
    ViewerProc->>Pipe: conn.send()
    Pipe->>Kernel: _conn.recv() via event_thread
    Kernel->>Kernel: _default_event_handler(event_type, data)

    Note over Kernel, ViewerProc: Le noyau résout les mathématiques et met à jour la scène
    Kernel->>Pipe: _send(SceneUpdateOp.UPDATE, ScenePayload)
    Pipe->>ViewerProc: cmd_queue.get_nowait()
    ViewerProc->>Scene: apply_patch(payload)
```
---
```mermaid
graph TD
    Mouse[Événements Souris Panda3D] --> MH[MouseHandler]
    Keyboard[Événements Clavier Panda3D] --> SR[ShortcutRegistry]

    subgraph Couche de Contrôle ["bot.control"]
        MH --> |Vérification survol/sélection| RP[RayPicker]
        MH --> |Calcul projection 3D| CM[ConstraintManager]
        MH --> |Délégation gestuelle| GT[GestureTracker]

        SR --> |Enregistrement de touches| SB[SequenceBuffer]
        SR --> |Évaluation des maintiens| GT
    end

    RP -.-> |pick_entry| Col[CollisionTraverser]
    CM -.-> |mouse_to_constrained_axis| Plane[Plane / Math]

    MH --> |Déclenche| CB[on_event_cb]
    SR --> |Déclenche| CB

    CB --> |Format ViewEvent| IPC[Pipe vers Processus Parent]
```

---

```mermaid
classDiagram
    class Observable {
        -_observers: list
        +add_observer(observer)
        +remove_observer(observer)
        #_notify_observers()
    }

    class CADModel {
        +scale_factor: float
        +add_point(coords, mesh_size)
        +get_curve_discretization()
    }

    class SplineModel {
        +curves: list
        +add_curve(type, degree, control_points)
        +move_control_point(tag, cp_index, new_pt)
    }

    class Adapter {
        <<Protocol>>
        +bind_update(callback)
        +unbind_update()
        +get_delta_load()
        +handle_event(event)
    }

    class Viewer {
        -_adapter: Adapter
        -_process: Process
        +connect_models(cad_model, spline_model)
        +run()
        -_dispatch_commands(commands)
    }

    Observable <|-- CADModel
    Observable <|-- SplineModel

    Adapter <|-- CADAdapter
    Adapter <|-- SplineAdapter
    Adapter <|-- CompositeAdapter

    CompositeAdapter *-- Adapter : agrège

    CADAdapter --> CADModel : observe
    SplineAdapter --> SplineModel : observe

    Viewer o-- Adapter : utilise
```

---

```mermaid
stateDiagram-v2
    [*] --> Idle

    Idle --> Hover : Survol (RayPicker détecte "cp")
    Hover --> Idle : Curseur quitte le "cp"
    Hover --> CP_PICK_START : Clic gauche (left_down=True)

    CP_PICK_START --> CP_DRAG : Mouvement souris (dragging_cp=True)
    CP_DRAG --> CP_DRAG : update_cp_drag() & mouse_to_constrained_axis()

    CP_DRAG --> CP_PICK_END : Relâchement clic (left_down=False)
    CP_PICK_END --> Idle : _finalize_drag() (Émission ViewEventType.CP_PICK_END)
```

---

```mermaid
flowchart
    subgraph Processus Parent ["Domaine"]
        Model[Modèles : CAD / Spline] --> |Extrait données| Adapt[CADAdapter / SplineAdapter]
        Adapt --> |pack_curve_delta| Dct[Dictionnaire CurveDelta]
        Dct --> |floats_to_bytes| Bytes[Canaux Binaires Float32]
        Bytes --> Payload[ScenePayload]
    end

    Payload --> |Sérialisation IPC Pipe| ChildProc


    subgraph Processus Enfant ["Rendu"]
        ChildProc[Pipe Reader] --> Loader[payload_to_geom_data]
        Loader --> |bytes_to_point_list| Pts[Listes imbriquées Python]
        Pts --> Builder[Scene._build_from_data]
        Builder --> App[CurveApp]
        App --> |GeomVertexData| Panda[Panda3D Render]
    end
```