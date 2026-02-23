from panda3d.core import OrthographicLens, PerspectiveLens
from direct.showbase.InputStateGlobal import inputState
from direct.showbase.DirectObject import DirectObject
from panda3d.core import OrthographicLens, LineSegs, NodePath
from panda3d.core import Point2, LVector3, LPoint3
from direct.interval.IntervalGlobal import Sequence, Parallel, LerpFunc

class CameraController(DirectObject):
    def __init__(self, base, view):
        DirectObject.__init__(self)
        self.base = base
        self.view = view
        self.is_animating = False
        # Vitesse de déplacement de la caméra
        self.panSpeed = 3
        # Correction : On récupère la lentille actuelle de la caméra
        # base.camLens est un raccourci pratique dans Panda3D
        self.lens_2d = self.base.camLens 
        
        # On s'assure que c'est une lentille orthographique pour la 2D
        if not isinstance(self.lens_2d, OrthographicLens):
            self.lens_2d = OrthographicLens()
            self.base.cam.node().setLens(self.lens_2d)

        # dummy node for camera, we will rotate the dummy node for camera rotation
        self.base.camera_focal_node =self.base.render.attachNewNode('cam_node')

        # the camera
        self.base.camera.reparentTo(self.base.camera_focal_node)
        self.base.camera.lookAt(self.base.camera_focal_node)
        self.base.camera.setY(-20)  # camera distance from model

        # On s'abonne aux messages envoyés par le KeyboardHandler
        self.accept("cmd_pan", self.handle_pan)
        self.accept("cmd_center_camera", self.recenter)
        self.accept("cmd_zoom", self.handle_zoom)
        self.accept("cmd_align_plane", self.align_to_plane)
        self.accept("cmd_rotate", self.handle_rotate)
        # For the gizmo update
        taskMgr.add(self.update_view_task, "UpdateViewTask")

        self.keyboard_speed = 20.0 # Vitesse ajustable
        taskMgr.add(self.update_keyboard_pan, "KeyboardPanTask")

        # Création et attachement du marqueur au pivot
        self.focal_marker = self.create_focal_marker()
        self.focal_marker.reparentTo(self.base.render)
        # On désactive le rendu des lumières sur la croix pour qu'elle soit toujours brillante
        self.focal_marker.setLightOff()
        # On s'assure qu'elle s'affiche au-dessus du reste si besoin
        self.focal_marker.setBin("fixed", 40)
        self.focal_marker.setDepthTest(False) # Optionnel: pour la voir à travers les objets
        
        self.focal_marker.hide() # Cachée par défaut
        
        # Abonnement pour basculer l'affichage
        self.accept("cmd_toggle_marker", self.toggle_marker)

    def apply_settings(self, settings: dict):
        """Reçoit un dictionnaire de valeurs 'propres'."""
        if 'pan_speed' in settings:
            self.pan_speed = settings['pan_speed']
            
        if 'bg_color' in settings:
            self.base.set_background_color(settings['bg_color'])
            
        if 'line_thickness' in settings and hasattr(self, 'focal_marker'):
            self.focal_marker.setRenderModeThickness(settings['line_thickness'])
    def update_keyboard_pan(self, task):
        if self.is_animating:
            return task.cont

        # On récupère le temps écoulé depuis la dernière image pour la fluidité
        dt = globalClock.getDt()
        move_dist = self.keyboard_speed * dt
        
        # Vecteurs de direction
        dx = 0
        dz = 0

        if inputState.isSet('left'):  dx -= move_dist
        if inputState.isSet('right'): dx += move_dist
        if inputState.isSet('up'):    dz += move_dist
        if inputState.isSet('down'):  dz -= move_dist

        # Si un mouvement est détecté, on l'applique relativement à la caméra
        if dx != 0 or dz != 0:
            # On déplace le pivot (focal_node) sur les axes X et Z de la caméra
            self.base.camera_focal_node.setPos(self.base.camera, 
                                              self.base.camera_focal_node.getPos(self.base.camera) 
                                              + LVector3(dx, 0, dz))
        
        return task.cont

    # Création et attachement du marqueur au pivot
        self.focal_marker = self.create_focal_marker()
        self.focal_marker.reparentTo(self.base.camera_focal_node)
        
        # On désactive le rendu des lumières sur la croix pour qu'elle soit toujours brillante
        self.focal_marker.setLightOff()
        # On s'assure qu'elle s'affiche au-dessus du reste si besoin
        self.focal_marker.setBin("fixed", 40)
        self.focal_marker.setDepthTest(False) # Optionnel: pour la voir à travers les objets
        
        self.focal_marker.hide() # Cachée par défaut
        
        # Abonnement pour basculer l'affichage
        self.accept("cmd_toggle_marker", self.toggle_marker)

    def toggle_marker(self):
        if self.focal_marker.isHidden():
            self.focal_marker.show()
        else:
            self.focal_marker.hide()

    def align_to_plane(self, axis):
        if self.is_animating: return
        
        size = self.view.model.bounds['size']
        max_dim = max(size)
        dist = max_dim * 2.5

        # Valeurs cibles pour le pivot (HPR)
        # On définit quel angle le pivot doit prendre pour présenter la bonne face
        if axis == "x":
            target_hpr = LVector3(90, 0, 0)
        elif axis == "y":
            target_hpr = LVector3(0, 0, 0)
        elif axis == "z":
            target_hpr = LVector3(0, -90, 0)

        self.is_animating = True
        duration = 0.5
        
        anim = Parallel(
            # 1. On fait pivoter le focal_node sur lui-même (là où il se trouve)
            self.base.camera_focal_node.hprInterval(duration, target_hpr, blendType='easeInOut'),
            
            # 2. On s'assure que la caméra est bien placée derrière ce pivot
            # On ne change que son Z local (profondeur en ortho) pour garder le cadrage
            self.base.camera.posInterval(duration, LPoint3(0, -dist, 0), blendType='easeInOut'),
            self.base.camera.hprInterval(duration, LVector3(0, 0, 0), blendType='easeInOut')
        )
        anim.setDoneEvent("unlock_camera")
        self.acceptOnce("unlock_camera", self.unlock)
        anim.start()

    def unlock(self):
        self.is_animating = False

    # def handle_pan(self, dx, dz):
    #     # direction [dx, dz] envoyée par messenger.send
    #     speed = 10.0 * globalClock.getDt()
        
    #     # On déplace la caméra sur son axe local X et Z
    #     self.base.camera.setX(self.base.camera, dx * speed)
    #     self.base.camera.setZ(self.base.camera, dz * speed)

    def handle_pan(self, dx, dz):
        if self.is_animating: return
        speed = 10.0 * globalClock.getDt()
        focal = self.base.camera_focal_node
        focal.setZ(focal, dz * speed)
        focal.setX(focal, dx * speed)

    def handle_rotate(self, dx, dy):
        if self.is_animating: return
        focal = self.base.camera_focal_node
        d_h = dx * 100.0
        d_p = dy * 100.0
        focal.setH(focal.getH() - d_h)
        focal.setP(focal.getP() + d_p)

    def recenter(self):
        """Recentrage sur la scène en conservant l'angle de vue actuel."""
        if self.is_animating: return

        # 1. Calculer le centre et la taille de la scène (tous les objets)
        center = self.view.model.bounds['center']
        size = self.view.model.bounds['size']
        max_dim = max(size)
        
        target_focal_pos = LPoint3(center[0], center[1], center[2])
        
        # 2. CALCUL CRUCIAL : Conserver le point de vue
        # On ne touche PAS au HPR (rotation) du focal_node ni de la caméra.
        # On calcule juste la nouvelle distance de recul nécessaire.
        dist = max_dim * 2.0 
        target_cam_pos = LPoint3(0, -dist, 0) # Position locale derrière le pivot

        self.is_animating = True
        duration = 0.5
        
        # 3. Animation
        anim = Parallel(
            # On déplace le pivot vers le nouveau centre
            self.base.camera_focal_node.posInterval(duration, target_focal_pos, blendType='easeInOut'),
            
            # On anime UNIQUEMENT la position locale de la caméra (le recul/zoom)
            # Sans toucher au HPR, elle garde son orientation actuelle
            self.base.camera.posInterval(duration, target_cam_pos, blendType='easeInOut'),
            
            # On ajuste la lentille orthographique pour englober la taille
            LerpFunc(self.set_lens_size, 
                     fromData=self.lens_2d.getFilmSize().getX(), 
                     toData=max_dim * 1.5, 
                     duration=duration)
        )
        
        anim.setDoneEvent("unlock_camera")
        self.acceptOnce("unlock_camera", self.unlock)
        anim.start()

    def set_lens_size(self, t):
        """Fonction utilitaire pour animer la taille de la lentille."""
        self.lens_2d.setFilmSize(t)

    def handle_zoom(self, factor):
        if self.is_animating: return
        """Zoom interactif en modifiant la taille du film de la lentille."""
        # 1. Récupérer la taille actuelle du film (LVecBase2f)
        current_size = self.lens_2d.getFilmSize()
        
        # 2. Calculer la nouvelle taille
        # Si factor = 1.1, on agrandit le film (donc on dézoome)
        # Si factor = 0.9, on réduit le film (donc on zoome vers l'objet)
        new_x = current_size.getX() * factor
        new_y = current_size.getY() * factor
        
        # 3. Appliquer la nouvelle taille
        self.lens_2d.setFilmSize(new_x, new_y)


    def create_focal_marker(self):
        """Crée une petite croix 3D simple."""
        lines = LineSegs()
        lines.setThickness(2.0)
        
        # Axe X (Rouge)
        lines.setColor(1, 0, 0, 1)
        lines.moveTo(-0.5, 0, 0)
        lines.drawTo(0.5, 0, 0)
        
        # Axe Y (Vert)
        lines.setColor(0, 1, 0, 1)
        lines.moveTo(0, -0.5, 0)
        lines.drawTo(0, 0.5, 0)
        
        # Axe Z (Bleu)
        lines.setColor(0, 0, 1, 1)
        lines.moveTo(0, 0, -0.5)
        lines.drawTo(0, 0, 0.5)
        
        # Création du NodePath
        marker_node = lines.create()
        return NodePath(marker_node)

    def update_view_task(self, task):
        # Position du marqueur sur le pivot dans le monde
        self.focal_marker.setPos(self.base.camera_focal_node.getPos(self.base.render))
        # Rotation du marqueur = Rotation du monde (0,0,0)
        self.focal_marker.setHpr(self.base.render, 0, 0, 0)

        # Rotation du Gizmo = Rotation GLOBALE de la caméra
        # On utilise l'inverse de la rotation caméra pour orienter le monde dans le Gizmo
        cam_quat = self.base.camera.getQuat(self.base.render)
        self.view.gizmo.update(cam_quat)
        
        return task.cont