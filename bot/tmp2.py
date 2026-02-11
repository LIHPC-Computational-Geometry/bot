from panda3d.core import *
from direct.showbase.ShowBase import ShowBase
import math
import sys


class Picker(object):
    def __init__(self, base):
        # CHANGED: combine all required masks
        mask = GeomNode.getDefaultCollideMask()
        mask |= BitMask32.bit(12)
        self.base = base
        self.queue = CollisionHandlerQueue()
        self.pickerNode = CollisionNode('MouseRay')
        self.pickerNP = self.base.camera.attachNewNode(self.pickerNode)
        # CHANGED: set "from" collision mask to the new combined version
        self.pickerNode.setFromCollideMask(mask)
        self.pickerRay = CollisionRay()
        self.pickerNode.addSolid(self.pickerRay)
        self.traverser = CollisionTraverser()
        self.traverser.addCollider(self.pickerNP, self.queue)

    def __call__(self, *args, **kwargs):
        mpos = kwargs.get('mpos', None if not args else args[0])
        return self.get_object_hit(mpos)

    def get_object_hit(self, mpos=None):
        if mpos is None:
            if not self.base .mouseWatcherNode.hasMouse():
                return None
            mpos = self.base .mouseWatcherNode.getMouse()

        self.pickerRay.setFromLens(self.base .camNode, mpos.getX(), mpos.getY())
        self.traverser.traverse(self.base.render)

        if not self.queue.getNumEntries():
            return None

        self.queue.sortEntries()
        np = self.queue.getEntry(0).getIntoNodePath()
        while np != self.base.render:
            if np.getTag('pickable') == 'true' and not np.isHidden():
                return np
            np = np.getParent()
        return None


class CurvePickingDemo(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        # Désactive la gestion de caméra par défaut
        self.disableMouse()
        # dummy node for camera, we will rotate the dummy node for camera rotation
        self.camera_focal_node =self.render.attachNewNode('cam_node')

        # the camera
        self.camera.reparentTo(self.camera_focal_node)
        # Positionne la caméra pour une vue orthogonale (2D)
        self.camera.setPos(0, 0, 50)
        self.camera.lookAt(0, 0, 0)


        # Ajoute un système de collision
        self.setup_collision()
        self.is_selected = False

        self.create_curve([(0,0,0),(10,0,0),(10,10,0)])



        # camera zooming
        self.accept('escape', sys.exit)
        self.accept('wheel_up', lambda: self.camera.setY(self.camera.getY() + 200 * globalClock.getDt()))
        self.accept('wheel_down', lambda: self.camera.setY(self.camera.getY() - 200 * globalClock.getDt()))
        self.accept('c', lambda: self.recenter())

        self.heading = 0
        self.pitch = 0
        self.panSpeed = 2

        # Accepte les entrées clavier
        self.accept('arrow_left', self.panLeft)
        self.accept('arrow_right', self.panRight)
        self.accept('arrow_up', self.panUp)
        self.accept('arrow_down', self.panDown)

    def axis(self, size=1, loc=(0, 0, 0)):
        ax = LineSegs()
        l = size / 2
        # Red X axis
        ax.setColor(1, 0, 0, 1)
        ax.moveTo(loc[0] - l, loc[1], loc[2])
        ax.drawTo(loc[0] + l, loc[1], loc[2])

        # Green Y axis
        ax.setColor(0, 1, 0, 1)
        ax.moveTo(loc[0], loc[1] - l, loc[2])
        ax.drawTo(loc[0], loc[1] + l, loc[2])

        # Blue Z axis
        ax.setColor(0, 0, 1, 1)
        ax.moveTo(loc[0], loc[1], loc[2] - l)
        ax.drawTo(loc[0], loc[1], loc[2] + l)

        # Create the NodePath object to attach it into the scene graph
        axis_node = ax.create()
        axis_np = NodePath(axis_node)
        axis_np.reparentTo(self.render)

        return axis_np
    def create_curve(self, points, thickness=5):
        # Crée la courbe (exemple : sinusoïde)
        lines = LineSegs()

        lines.setThickness(thickness)
        if points:
            lines.moveTo(points[0][0], points[0][1], points[0][2])
            for p in points[1:]:
                lines.drawTo(p[0], p[1], p[2])
            # Attache la courbe à la scène
            curve_geom = lines.create()
            curve_np = self.render.attachNewNode(curve_geom)
            curve_np.setColor(1,0,0,1)
            for (x1, y1, z1), (x2, y2, z2) in zip(points[:-1], points[1:]):
                tubeRadius = 0.5
                tube = CollisionTube(x1, y1, z1, x2, y2, z2, tubeRadius)
                cNode = CollisionNode('wireCollisionTube')
                cNode.setIntoCollideMask(BitMask32.bit(12))
                cNode.addSolid(tube)
                cNode_path = NodePath(cNode)
                cNode_path.reparentTo(curve_np)

                #cNode_path.show()
        else:
            exit(0)


    def setup_collision(self):
        mask = GeomNode.getDefaultCollideMask()
        mask |= BitMask32.bit(12)
        # Crée un nœud de collision
        self.picker_node = CollisionNode('picker')
        self.picker_np = self.camera.attachNewNode(self.picker_node)
        self.picker_node.setFromCollideMask(GeomNode.getDefaultCollideMask())
        # CHANGED: set "from" collision mask to the new combined version
        self.picker_node.setFromCollideMask(mask)
        self.picker_ray = CollisionRay()
        self.picker_node.addSolid(self.picker_ray)
        # Crée un CollisionTraverser et un CollisionHandlerQueue
        self.traverser = CollisionTraverser()
        self.queue = CollisionHandlerQueue()
        # Ajoute le nœud de collision au traverser
        self.traverser.addCollider(self.picker_np, self.queue)

        # Configure la souris pour le picking
        # Accepte la pression de la touche Espace
        self.accept('space', self.try_pick_curve)


    def try_pick_curve(self):
        # Vérifie si la souris est proche de la courbe
        if self.mouseWatcherNode.hasMouse():
            mouse_pos = self.mouseWatcherNode.getMouse()
            self.picker_ray.setFromLens(self.camNode, mouse_pos.getX(), mouse_pos.getY())
            # Traverse la scène pour détecter les collisions
            self.traverser.traverse(self.render)
            # Vérifie si le rayon a touché la courbe
            if self.queue.getNumEntries() > 0:
                self.queue.sortEntries()
                pickedObj = self.queue.getEntry(0).getIntoNodePath()
                #pickedObj = pickedObj.findNetTag('pickable')
                self.toggle_selection(pickedObj.parent)

    def toggle_selection(self, selection):
        print("toggle_selection")

        self.is_selected = not self.is_selected
        if self.is_selected:
            selection.clearColor()
            selection.setColor(1,0,0,0)
        else:
            selection.clearColor()
            selection.setColor(0,0,1,0)
           # selection.node().getGeom(0).setThickness(2.0)
        # Met à jour la géométrie
       # self.curve_geom.removeNode()
        #self.curve_geom = self.lines.create()
        #self.curve_node.attachNewNode(self.curve_geom)

    def update(self, task):
        # Met à jour le traverser de collision
      #  self.traverser.traverse(self.render)
        return task.cont



    def panLeft(self):
        print("to left " + str(self.panSpeed))
        self.camera_focal_node.setX(self.camera_focal_node, self.panSpeed)


    def panRight(self):
        self.camera_focal_node.setX(self.camera_focal_node, -self.panSpeed)


    def panUp(self):
        self.camera_focal_node.setZ(self.camera_focal_node, -self.panSpeed)


    def panDown(self):
        self.camera_focal_node.setZ(self.camera_focal_node, self.panSpeed)


    def recenter(self):
        self.camera_focal_node.setPos(0, 0, 0)

        # Define a procedure to move the camera.


    def move(self, task):
        if self.mouseWatcherNode.hasMouse():
            mouse_pos = self.mouseWatcherNode.getMouse()
            if self.prevMouse is None:
                self.prevMouse = Point2(mouse_pos)
            if inputState.isSet('shift'):
                dx = mouse_pos.getX() - self.prevMouse.getX()
                dz = mouse_pos.getY() - self.prevMouse.getY()
                self.camera_focal_node.setZ(self.camera_focal_node, dz * self.panSpeed)
                self.camera_focal_node.setX(self.camera_focal_node, dx * self.panSpeed)
            else:
                mouse_pos = self.mouseWatcherNode.getMouse()
                md = self.win.getPointer(0)
                x = md.getX()
                y = md.getY()

                d_heading, d_pitch = (mouse_pos - self.prevMouse) * 100.
                self.camera_focal_node.set_hpr(self.camera_focal_node.get_h() - d_heading,
                                               self.camera_focal_node.get_p() + d_pitch, 0.)

            # self.focal_cross.setHpr(-self.heading, -self.pitch, 0)

            self.prevMouse = Point2(mouse_pos)

        return task.cont


app = CurvePickingDemo()
app.taskMgr.add(app.update, "update")
app.run()
