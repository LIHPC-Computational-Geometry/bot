import sys

from direct.showbase.InputStateGlobal import inputState
from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from panda3d.core import Point2, AmbientLight, Vec4, DirectionalLight, Vec3

from bot.view.ActorBuilder import ActorBuilder

import bot.model.geom.api as geom
class MyApp(ShowBase):
    def __init__(self, filename):
        ShowBase.__init__(self)
        self.disableMouse()
        geom.initialize()
        geom.import_step(filename)
        print('model info - points=', len(geom.get_point_tags()), ', curves=', len(geom.get_edge_tags()), ', surfaces=', len(
            geom.get_face_tags()))
        vertices, triangles = geom.triangulate()
        print(vertices)
        print(triangles)

        ActorBuilder(self.render).geom_from_mesh(vertices, triangles)
 #       cube  = ActorBuilder(self.render).cube(2, (0, 0, 0))
  #      cube2 = ActorBuilder(self.render).cube(1, (2, 1, 0))
     #   ActorBuilder(self.render).tetrahedron()
        inputState.watchWithModifiers('shift', 'shift')
        self.prevMouse = None

        # dummy node for camera, we will rotate the dummy node for camera rotation
        self.camera_focal_node =self.render.attachNewNode('cam_node')

        self.focal_axis = ActorBuilder(self.render).axis()
        self.focal_axis.reparentTo(self.camera_focal_node)
        self.focal_axis.setCompass()
        # the camera
        self.camera.reparentTo(self.camera_focal_node)
        self.camera.lookAt(self.camera_focal_node)
        self.camera.setY(-20)  # camera distance from model

        # camera zooming
        self.accept('escape', sys.exit)
        self.accept('wheel_up', lambda: self.camera.setY(self.camera.getY() + 200 * globalClock.getDt()))
        self.accept('wheel_down', lambda: self.camera.setY(self.camera.getY() - 200 * globalClock.getDt()))
        self.accept('c', lambda: self.recenter())

        self.heading = 0
        self.pitch = 0

        self.taskMgr.add(self.move, "movement")
        # Vitesse de déplacement de la caméra
        self.panSpeed = 2

        # Accepte les entrées clavier
        self.accept('arrow_left', self.panLeft)
        self.accept('arrow_right', self.panRight)
        self.accept('arrow_up', self.panUp)
        self.accept('arrow_down', self.panDown)
        self.add_lighting()


    def panLeft(self):
        print("to left "+str(self.panSpeed))
        self.camera_focal_node.setX(self.camera_focal_node, self.panSpeed)


    def panRight(self):
        self.camera_focal_node.setX(self.camera_focal_node, -self.panSpeed)


    def panUp(self):
        self.camera_focal_node.setZ(self.camera_focal_node, -self.panSpeed)


    def panDown(self):
        self.camera_focal_node.setZ(self.camera_focal_node, self.panSpeed)

    def recenter(self):
        self.camera_focal_node.setPos(0,0,0)

        # Define a procedure to move the camera.
    def move(self, task):
        if self.mouseWatcherNode.hasMouse():
            mouse_pos = self.mouseWatcherNode.getMouse()
            if self.prevMouse is None:
                self.prevMouse = Point2(mouse_pos)
            if inputState.isSet('shift'):
                dx = mouse_pos.getX() - self.prevMouse.getX()
                dz = mouse_pos.getY() - self.prevMouse.getY()
                self.camera_focal_node.setZ(self.camera_focal_node, dz*self.panSpeed)
                self.camera_focal_node.setX(self.camera_focal_node, dx* self.panSpeed)
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

    def add_lighting(self):
        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor(Vec4(0.3, 0.3, 0.3, 1))
        directionalLight = DirectionalLight("directionalLight")
        directionalLight.setColor(Vec4(1, 1, 1, 1))
        directionalLight.setDirection(Vec3(-1, -1, -1))

        self.render.setLight(self.render.attachNewNode(ambientLight))
        self.render.setLight(self.render.attachNewNode(directionalLight))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    app = MyApp("data/cube.step")
    app.run()
