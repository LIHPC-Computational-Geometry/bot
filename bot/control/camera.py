from panda3d.core import LPoint3, LVector3, OrthographicLens, LineSegs, NodePath
from direct.interval.IntervalGlobal import Parallel, LerpFunc, Sequence, Func


class CameraController:
    """
    Orthographic camera controller for the 3D view.

    Manages the pivot node (focal_node), the orthographic lens, and smooth
    animations for rotation, pan, zoom and standard-plane alignment.
    Reacts to Panda3D messenger events: ``cmd_rotate``, ``cmd_pan``,
    ``cmd_zoom``, ``cmd_center`` and ``cmd_align_plane``.
    """

    # TODO: check settings maybe a configuration error
    def __init__(self, base, scene, settings):
        """
        Set up the orthographic camera and its node hierarchy.

        Args:
            base:     Panda3D ShowBase instance.
            scene:    Scene object exposing ``geom_node`` and ``bounds``.
            settings: Camera configuration dict (speeds, animation duration…).
        """
        self.base = base
        self.scene = scene
        self.is_animating = False
        self.base.disableMouse()
        self.model_radius = 0

        # 1. Configuration de la Lentille Orthographique
        self.lens = OrthographicLens()
        self.lens.setFilmSize(20, 20)
        self.base.cam.node().setLens(self.lens)

        # 2. Hiérarchie : focal_node (Pivot) -> camera
        self.focal_node = self.base.render.attachNewNode("camera_pivot")
        self.base.camera.reparentTo(self.focal_node)
        self.base.camera.setPos(0, -100, 0)
        # 3. Marqueur de pivot (la croix)
        self.marker = self.create_marker()
        self.marker.reparentTo(self.base.render)

        # Écoute des ordres venant des autres classes
        self.base.accept("cmd_rotate", self.handle_rotate)
        self.base.accept("cmd_pan", self.handle_pan)
        self.base.accept("cmd_center", self.recenter)
        self.base.accept("cmd_zoom", self.handle_zoom)
        self.base.accept("cmd_align_plane", self.align_to_plane)

        # Vitesse de déplacement au clavier
        self.key_pan_speed = 2.0

        # Task pour maintenir le marqueur et le gizmo
        self.base.taskMgr.add(self.update_task, "CameraUpdateTask")
        # Configure la camera par rapport au contenu de la scene
        self.refresh_scene()

    def refresh_scene(self):
        """
        Recompute camera parameters from the current scene geometry.

        Updates the pivot position, lens film size, near/far clip planes and
        dynamic zoom bounds so the whole model fits in view.
        """
        # 1. Get data to characteriza
        bounds = self.scene.geom_node.getBounds()
        center = bounds.getCenter()
        radius = bounds.getRadius()
        if radius <= 0:
            radius = 1  # Sécurité si modèle vide

        # 2. Positionner le pivot au centre de l'objet
        self.focal_node.setPos(center)
        self.model_radius = radius
        self.model_center = center
        # 3. Ajuster la lentille avec une MARGE (ex: 1.2 pour 20% d'espace vide autour)
        view_size = radius * 2.2
        self.lens.setFilmSize(view_size, view_size)

        # 4. Adujst the limits of automatic zoom
        self.min_zoom = self.model_radius * 0.05
        self.max_zoom = self.model_radius * 20.0

        # 5. Positionner la caméra par rapport au pivot
        # On la recule de 2x le rayon pour être sûr de ne pas être "dedans"
        self.base.camera.setPos(0, -self.model_radius * 2, 0)

        # 6. Ajuster la profondeur de rendu (Near/Far)
        # Très important pour ne pas que l'objet soit "tronçonné"
        limit = max(100000, self.model_radius * 1000)
        self.lens.setNear(0.1)
        self.lens.setFar(limit * 2)

    def create_marker(self):
        """
        Build an RGB trihedron marker showing the pivot position.

        Returns:
            NodePath: Panda3D node containing the three coloured axis segments.
        """
        ls = LineSegs()
        ls.setThickness(2)
        for i, col in enumerate([(1, 0, 0, 1), (0, 1, 0, 1), (0, 0, 1, 1)]):
            ls.setColor(col)
            v = LVector3(0, 0, 0)
            v[i] = 0.5
            ls.moveTo(0, 0, 0)
            ls.drawTo(v)
        return NodePath(ls.create())

    def handle_rotate(self, dx, dy):
        """
        Rotate the camera around the pivot node.

        Args:
            dx: Normalised horizontal delta (screen space, -1..1).
            dy: Normalised vertical delta (screen space, -1..1).
        """
        if self.is_animating:
            return
        sens = 100.0
        new_h = self.focal_node.getH() - dx * sens
        new_p = self.focal_node.getP() + dy * sens
        self.focal_node.setHpr(new_h, max(min(new_p, 89), -89), 0)

    def handle_pan(self, dx, dy):
        """
        Translate the pivot in the camera plane (drag-to-pan).

        Displacement is scaled by the current lens film size so that one unit
        of screen movement always corresponds to the same world distance.

        Args:
            dx: Normalised horizontal delta (screen space, -1..1).
            dy: Normalised vertical delta (screen space, -1..1).
        """
        if self.is_animating:
            return

        # Largeur de la vue actuelle
        fs = self.lens.getFilmSize().getX()

        # En mode Ortho, l'écran fait 2 unités de large (-1 à 1)
        # On divise par 2 pour que le ratio soit de 1:1
        # On inverse dx et dy pour l'effet "poignée" (drag)
        move_x = -dx * (fs * 0.5)
        move_z = -dy * (fs * 0.5)

        # On déplace par rapport à la caméra pour respecter l'orientation de l'écran
        self.focal_node.setPos(self.base.camera, LVector3(move_x, 0, move_z))

    def handle_zoom(self, factor):
        """
        Zoom in or out by scaling the orthographic lens film size.

        Near/far clip planes are pushed out proportionally to prevent clipping.

        Args:
            factor: Multiplier applied to the current film size
                    (< 1 zooms in, > 1 zooms out).
        """
        if self.is_animating:
            return

        # 1. Calculer la nouvelle taille de vue
        current_size = self.lens.getFilmSize().getX()
        new_size = current_size * factor

        # 2. Lever la restriction de taille (on garde une sécurité minimale)
        if 0.00001 < new_size < 100000:
            self.lens.setFilmSize(new_size, new_size)

            # 3. LEVIER DE RESTRICTION : On pousse les plans de coupe très loin
            # On s'assure que la profondeur de vue est 10x plus grande que l'objet
            # pour éviter tout "clipping" (disparition)

            limit = max(new_size * 1000, self.model_radius * 1000)
            self.lens.setNear(-limit)
            self.lens.setFar(limit)

    def recenter(self):
        """
        Smoothly move the pivot back to the geometric centre of the model.

        Only the pivot position is animated; rotation and zoom are left
        unchanged so the user keeps their current viewing angle.
        """
        if self.is_animating:
            return
        self.is_animating = True

        # On récupère le centre réel de l'objet calculé dans analyze_model
        # target_pos est un LPoint3 (le centre géométrique du modèle)
        target_pos = self.model_center

        duration = 0.4  # Un peu plus rapide pour un recadrage fluide

        # On ne crée qu'UN SEUL intervalle : la position.
        # On ne touche NI au HPR (rotation) NI au FilmSize (zoom).
        self.cam_anim = self.focal_node.posInterval(
            duration, target_pos, blendType="easeInOut"
        )
        # Séquence pour déverrouiller à la fin
        Sequence(self.cam_anim, Func(self._unlock)).start()

    def _unlock(self):
        """Release the animation lock so user input is accepted again."""
        self.is_animating = False

    def align_to_plane(self, axis):
        """
        Animate to a standard orthographic view aligned with the given axis.

        Simultaneously rotates the pivot, recentres it on the model, and
        adjusts the lens to frame the geometry.

        Args:
            axis: One of ``"x"`` (right view), ``"y"`` (front view) or
                  ``"z"`` (top view).
        """
        if self.is_animating:
            return

        # 1. Définir les rotations cibles (Heading, Pitch, Roll)
        if axis == "z":  # Vue de dessus (Top)
            target_hpr = LPoint3(0, -90, 0)
        elif axis == "y":  # Vue de face (Front)
            target_hpr = LPoint3(0, 0, 0)
        elif axis == "x":  # Vue de côté (Right)
            target_hpr = LPoint3(90, 0, 0)
        else:
            return

        self.is_animating = True

        duration = 0.5
        # 2. Animation fluide de la rotation du pivot
        # On peut aussi combiner cela avec un recentrage automatique
        center = LPoint3(*self.scene.bounds["center"])
        max_dim = (
            max(self.scene.bounds["size"])
            if max(self.scene.bounds["size"]) > 0
            else 1.0
        )
        self.transition = Parallel(
            # 1. Aligne la rotation sur l'axe demandé
            self.focal_node.hprInterval(duration, target_hpr, blendType="easeInOut"),
            # 2. Déplace le pivot vers le centre réel du modèle
            self.focal_node.posInterval(duration, center, blendType="easeInOut"),
            LerpFunc(
                lambda s: self.lens.setFilmSize(s),
                fromData=self.lens.getFilmSize().getX(),
                toData=max_dim * 1.5,
                duration=duration,
                blendType="easeInOut",
            ),
        )

        # On lance et on déverrouille à la fin
        Sequence(self.transition, Func(self._unlock)).start()

        # Parallel(
        #     self.focal_node.hprInterval(duration, target_hpr, blendType='easeInOut'),
        #     self.focal_node.posInterval(duration, center, blendType='easeInOut'),
        #     LerpFunc(lambda s: self.lens.setFilmSize(s),
        #              fromData=self.lens.getFilmSize().getX(),
        #              toData=max_dim * 1.5,
        #              duration=duration,
        #              blendType='easeInOut'),
        #     name="AlignAnimation"
        # ).start()

        # taskMgr.doMethodLater(duration, self._unlock, "UnlockTask")

    def update_task(self, task):
        """
        Per-frame task: keep the pivot marker and gizmo in sync with the camera.

        Returns:
            task.cont to keep the task alive.
        """
        # Le marqueur suit le pivot
        self.marker.setPos(self.focal_node.getPos())
        # Mise à jour du Gizmo (orientation de la caméra vers le monde)
        if hasattr(self.scene, "gizmo"):
            self.scene.gizmo.update(self.base.camera.getQuat(self.base.render))
        return task.cont
