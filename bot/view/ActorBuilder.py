from panda3d.core import GeomVertexFormat, Geom, GeomVertexWriter, GeomVertexData, GeomLines, GeomNode, LineSegs, \
    NodePath, GeomTriangles, Vec4, Vec3, GeomVertexArrayFormat

import colorsys

class ColorGenerator:
    @staticmethod
    def generate_distinct_colors(n):
        """
        Generate n visually distinct RGB colors using HSV spacing.

        Args:
            n (int): Number of colors to generate.

        Returns:
            List of (r, g, b) tuples in [0, 1]
        """
        return [colorsys.hsv_to_rgb(i / n, 0.65, 1.0) for i in range(n)]


class ActorBuilder:
    def __init__(self, render):
        self.nb_actors = 0
        self.render = render

    def cube(self, size=1, location=(0, 0, 0)):
        v_format = GeomVertexFormat.getV3()
        v_data = GeomVertexData('cube', v_format, Geom.UHStatic)

        # add vertices
        vertex_writer = GeomVertexWriter(v_data, 'vertex')
        c = size / 2
        # Cube corners
        vertices = [
            (-c, -c, -c), (c, -c, -c), (c, c, -c), (-c, c, -c),
            (-c, -c, c), (c, -c, c), (c, c, c), (-c, c, c)
        ]

        for v in vertices:
            vertex_writer.addData3f(*v)
        # Wireframe representation
        lines = GeomLines(Geom.UHStatic)
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),
            (4, 5), (5, 6), (6, 7), (7, 4),
            (0, 4), (1, 5), (2, 6), (3, 7)
        ]

        for edge in edges:
            lines.addVertices(edge[0], edge[1])

        # Build the geometry and create a node
        geom = Geom(v_data)
        geom.addPrimitive(lines)
        node = GeomNode('wireframe_gnode')
        node.addGeom(geom)

        # Attacher le GeomNode à la scène
        cube = self.render.attachNewNode(node)
        cube.setPos(location[0], location[1], location[2])

        self.nb_actors += 1
        return cube

    def axis(self, size=1, loc=(0, 0, 0)):
        ax= LineSegs()
        l = size/2
        # Red X axis
        ax.setColor(1, 0, 0, 1)
        ax.moveTo(loc[0]-l, loc[1], loc[2])
        ax.drawTo(loc[0]+l, loc[1], loc[2])

        # Green Y axis
        ax.setColor(0, 1, 0, 1)
        ax.moveTo(loc[0], loc[1]-l, loc[2])
        ax.drawTo(loc[0], loc[1]+l, loc[2])

        # Blue Z axis
        ax.setColor(0, 0, 1, 1)
        ax.moveTo(loc[0], loc[1], loc[2]-l)
        ax.drawTo(loc[0], loc[1], loc[2]+l)

        # Create the NodePath object to attach it into the scene graph
        axis_node = ax.create()
        axis_np = NodePath(axis_node)
        axis_np.reparentTo(self.render)
        self.nb_actors += 1

        return axis_np

    def tetrahedron(self):
        # Define 4 points (vertices) of a tetrahedron
        vertices = [
            Vec3(1, 1, 1),  # vertex 0
            Vec3(-1, -1, 1),  # vertex 1
            Vec3(-1, 1, -1),  # vertex 2
            Vec3(1, -1, -1),  # vertex 3
        ]

        # Define triangular faces using indices into the vertex list
        faces = [
            (0, 1, 2),
            (0, 3, 1),
            (0, 2, 3),
            (1, 3, 2),
        ]

        v_format = GeomVertexFormat.get_v3n3c4()
        vdata = GeomVertexData('tetra', v_format, Geom.UHStatic)

        vertex_writer = GeomVertexWriter(vdata, 'vertex')
        normal_writer = GeomVertexWriter(vdata, 'normal')
        color_writer = GeomVertexWriter(vdata, 'color')

        for v in vertices:
            vertex_writer.addData3(v)
            normal_writer.addData3(v.normalized())  # Just use position as normal for simplicity
            color_writer.addData4(Vec4(0.8, 0.2, 0.3, 1))  # Orange-ish color

        triangles = GeomTriangles(Geom.UHStatic)

        for face in faces:
            triangles.addVertices(*face)

        geom = Geom(vdata)
        geom.addPrimitive(triangles)

        # Create a solid tetrahedron
        node = GeomNode('tetrahedron')
        node.addGeom(geom)
        solid_nodepath = self.render.attachNewNode(node)
        solid_nodepath.setTwoSided(True)
        edges = [
            (0, 1), (0, 2), (0, 3),
            (1, 2), (1, 3),
            (2, 3),
        ]
        self.create_edges(vertices, edges)

    def create_edges(self, vertices, edges):
        lines = LineSegs()
        lines.setThickness(2.0)
        lines.setColor(1, 1, 1, 1)  # Black

        for i, j in edges:
            lines.moveTo(vertices[i])
            lines.drawTo(vertices[j])

        edge_node = lines.create()
        self.render.attachNewNode(edge_node)

    def geom_from_mesh(self, vertices, surfaces):
        colors = ColorGenerator.generate_distinct_colors(len(surfaces))

        mesh_array_format = GeomVertexArrayFormat()#GeomVertexFormat.get_v3c4()
        mesh_array_format.addColumn("vertex", 3, Geom.NTFloat32, Geom.CPoint)
        mesh_array_format.addColumn("triangles", 3, Geom.NTInt32, Geom.COther)
        mesh_array_format.addColumn("color", 4, Geom.NTFloat32, Geom.CColor)
        mesh_format = GeomVertexFormat()
        mesh_format.addArray(mesh_array_format)
        mesh_format = GeomVertexFormat.registerFormat(mesh_format)
        mesh_data = GeomVertexData('mesh', mesh_format, Geom.UHStatic)

        vertex_writer = GeomVertexWriter(mesh_data, 'vertex')
        color_writer = GeomVertexWriter(mesh_data, 'color')

        for v in vertices:
            vec = Vec3(v)
            vertex_writer.addData3(vec)
            color_writer.addData4f(0.8, 0.2, 0.3, 1)  # Orange-ish color

            # Map from global node index to Panda3D vertex index
            index_map = {}
            for i, vertex in enumerate(vertices):
                vertex_writer.addData3f(*vertex)
                index_map[i - 1] = i  # Gmsh node tags start at 1

        geom = Geom(mesh_data)
        prim = GeomTriangles(Geom.UHStatic)
        for s in surfaces:
            for tri in s:
                try:
                    a = index_map[tri[0]]
                    b = index_map[tri[1]]
                    c = index_map[tri[2]]
                    prim.addVertices(a, b, c)
                except KeyError:
                    continue  # In case of missing nodes

        geom.addPrimitive(prim)

        # Create a solid tetrahedron
        node = GeomNode('mesh')
        node.addGeom(geom)
        solid_nodepath = self.render.attachNewNode(node)
        solid_nodepath.setTwoSided(True)
