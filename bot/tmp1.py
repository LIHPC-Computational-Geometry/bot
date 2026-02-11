from direct.showbase.ShowBase import ShowBase
from panda3d.core import LineSegs, CollisionNode, CollisionSegment, CollisionTraverser, CollisionHandlerQueue, CollisionRay


class LineClickApp(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

        # Créer une ligne
        ls = LineSegs()
        ls.setColor(1, 0, 0, 1)
        ls.moveTo(0, 0, 0)
        ls.drawTo(1, 1, 1)
        self.line_node = ls.create()
        self.line_np = self.render.attachNewNode(self.line_node)

        # Ajouter une collision
        collision_node = CollisionNode("line_collision")
        collision_segment = CollisionSegment(0, 0, 0, 1, 1, 1)
        collision_node.addSolid(collision_segment)
        self.collision_np = self.line_np.attachNewNode(collision_node)
        self.collision_np.show()

        # Configurer la détection de clics
        self.traverser = CollisionTraverser()
        self.queue = CollisionHandlerQueue()
        self.picker_node = CollisionNode("mouse_picker")
        self.picker_ray = CollisionRay()
        self.picker_node.addSolid(self.picker_ray)
        self.picker_np = self.camera.attachNewNode(self.picker_node)
        self.traverser.addCollider(self.picker_np, self.queue)

        # Ajouter une tâche pour gérer les clics
        self.accept("mouse1", self.handle_click)

    def handle_click(self):
        if self.mouseWatcherNode.hasMouse():
            mouse_pos = self.mouseWatcherNode.getMouse()
            self.picker_ray.setFromLens(self.camNode, mouse_pos.x, mouse_pos.y)
            self.traverser.traverse(self.render)

            if self.queue.getNumEntries() > 0:
                self.queue.sortEntries()
                for i in range(self.queue.getNumEntries()):
                    entry = self.queue.getEntry(i)
                    line_np = entry.getIntoNodePath().getParent()
                    self.update_line_appearance(line_np)

    def update_line_appearance(self, line_np):
        # Recréer la ligne avec une nouvelle couleur et épaisseur
        new_ls = LineSegs()
        new_ls.setColor(0, 1, 0, 1)  # Vert
        new_ls.moveTo(0, 0, 0)
        new_ls.drawTo(1, 1, 1)

        line_attrib = LineAttrib.make(3)  # Épaisseur de 3 pixels
        new_ls.setAttrib(line_attrib)

        new_node = new_ls.create()
        line_np.removeNode()
        line_np = self.render.attachNewNode(new_node)

        # Réappliquer la collision
        collision_node = CollisionNode("line_collision")
        collision_segment = CollisionSegment(0, 0, 0, 1, 1, 1)
        collision_node.addSolid(collision_segment)
        line_np.attachNewNode(collision_node)

app = LineClickApp()
app.run()
