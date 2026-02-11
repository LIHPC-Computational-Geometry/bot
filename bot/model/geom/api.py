import gmsh
import numbers

""""global value to indicate how to round floating numbers"""
nb_digit_rounding = 4


class Api:
    """
    The geometric model provides simple and basic function to load geometric files and to query a geometric model
    based on the OpenCascade technology. To do so, we totally rely on the gmsh library.
    """
    @staticmethod
    def initialize():
        """
        geom.api.Api.import_model(filename)

        initialize the gmsh context useful for the geometric model. This operation must be called before any
        other operations.
        """
        gmsh.initialize()
        gmsh.clear()
        # to avoid messages on the console
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMin", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMax", 5)

    @staticmethod
    def import_geo(filename):
        """
        geom.api.Api.import_model(filename)

        import the model contained in the file named `filenanme`, which is the path to
        the file to import

        Types:
        - `filenanme`: string
        """
        gmsh.model.occ.importShapes(filename)
        gmsh.model.occ.synchronize()


    @staticmethod
    def open_geo(filename):
        """
        geom.api.Api.open_geo(filename)

        open the file `filenanme`, which contains the path to
        the file to open (extension .geo)

        Types:
        - `filenanme`: string
        """
        gmsh.open(filename)
        gmsh.model.occ.synchronize()

    @staticmethod
    def finalize():
        """
        geom.api.Api.finalize()

        This operation must be called at the end of the program to finalize the gmsh context
        """
        gmsh.finalize()

    @staticmethod
    def synchronize():
        """
       geom.api.Api.synchronize()

        This operation must be invocated after applying geometric operations to be sure to have a consistent state.
        We advise to call this method before starting the meshing stage.
        """
        gmsh.model.occ.synchronize()


    @staticmethod
    def __get_cell_tags(dim):
        """
        Private method that returns the tags, i.e. the ids, of the cells of dimension dim.
        This operation is private and must not be called directly outside the scope of public operations of
        geom.api.Api

        Args:
        dim (int): An int included in [0,3].

        Raises:
        - ValueError: if 'dim' is not included in [0,3].
        - TypeError: if 'dim' is not an int.
        """
        if not isinstance(dim, int):
            raise TypeError("the parameter must be an int.")
        if dim < 0 or dim > 3:
            raise ValueError("the parameter must be an int comprised between 0 and 3.")

        info = gmsh.model.occ.getEntities(dim)
        tags = []
        for i, j in info:
            tags.append(j)
        return tags


    @staticmethod
    def get_point_tags():
        """
        geom.api.Api.get_point_tags(dim)

        returns the tags of all the points
        """
        return Api.__get_cell_tags(0)

    @staticmethod
    def get_curve_tags():
        """
        geom.api.Api.get_curve_tags(dim)

        return the tags of all the curves
        """
        return Api.__get_cell_tags(1)
    @staticmethod
    def get_surface_tags():
        """
        geom.api.Api.get_surface_tags(dim)

        return the tags of all the surfaces
        """
        return Api.__get_cell_tags(2)


    @staticmethod
    def getClosestPoint(dim, tag, coord):
        """
        geom.api.Api.getClosestPoint(dim, tag, coord)

        Get the points `closestCoord` on the entity of dimension `dim` (1 or 2) and
        tag `tag` to the points `coord`, by orthogonal projection. `coord` is given
        as x, y, z coordinates, concatenated: [p1x, p1y,
        p1z, p2x, ...]. The
        closest points can lie outside the (trimmed) entities: use `isInside()` to
        check.

        Return `closestCoord`, `parametricCoord`.

        Types:
        - `dim`: integer
        - `tag`: integer
        - `coord`: vector of doubles
        """
        if not isinstance(dim, int):
            raise TypeError("the dimension parameter (dim) must be an int.")
        if not isinstance(tag, int):
            raise TypeError("the tag parameter (tag) must be an int.")
        if not isinstance(dim, int):
            return isinstance(coord, (list,tuple)) and len(coord) == 3 and all(
                isinstance(x, numbers.Real) for x in coord)

            raise TypeError("the dimension parameter (dim) must be an int.")
        if dim < 1 or dim > 2:
            raise ValueError("the dim parameter must be an int comprised between 1 and 2.")

        return gmsh.model.getClosestPoint(dim, tag, coord)[0]

    @staticmethod
    def get_end_points(curve_tag):
        """
        geom.api.Api.get_end_points(curve_tag)

        Get the tags of the end points of the curve of id `curve_tag `
        Return `closestCoord`, `parametricCoord`.
        """
        data = gmsh.model.getAdjacencies(1, curve_tag)
        return data[1]

    @staticmethod
    def get_adjacent_curves_of_point(point_tag):

        # We check if the tag is an existing point tag
        if not point_tag in Api.get_point_tags() :
            raise ValueError("Invalid point tag")

        curves = []
        # Traverse all the model curves
        for curve_tag in Api.get_curve_tags():
            # get curve end points
            end_points = Api.get_end_points(curve_tag)
            if end_points[0] == point_tag :
                curves.append(curve_tag)
            elif end_points[1] == point_tag :
                curves.append(curve_tag)
        return curves

    def get_adjacent_points(self, curve_tag):
        points = []
        for adj in self.__l2p:
            if adj[0] is curve_tag:
                points.append(adj[1])
        return points

    def get_curves(self, face_tag):
        """
        Get all the curves that surround face defined by the tag face_tag

        This function accesses the Gmsh framework to extract a list of curves
        that define the boundary of a specified face. It utilizes the
        get_curve_loops method from the occ API. Only the primary set of
        curves is returned from the nested output.

        :param face_tag: The identifier tag of the target face in the Gmsh model.
        :type face_tag: int
        :return: A list of curve identifiers that form the boundary of the specified face.
        :rtype: list[int]
        """
        return gmsh.model.occ.get_curve_loops(face_tag)[1][0]

    def get_corners(self, face_tag):
        """
        Extracts and returns the corner points of a given face in a geometric model. The method analyzes
        the adjacency information of the face and identifies the common points between consecutive curves
        that make up the face to determine the corners.

        :param face_tag: The tag of the face for which corner points are to be determined.
        :type face_tag: int
        :return: A list of corner point tags that outline the geometry of the face.
        :rtype: list[int]
        """
        curves = gmsh.model.getAdjacencies(2, face_tag)[1]
        all_points = get_point_tags()
        corners = []
        for i_curve in range(0, len(curves)):
            j_index = i_curve - 1
            if i_curve == 0:
                j_index = len(curves) - 1
            prev_pnts = get_end_points(curves[j_index])
            current_pnts = get_end_points(curves[i_curve])
            common_pnt = 0
            if prev_pnts[0] == current_pnts[0]:
                common_pnt = current_pnts[0]
            elif prev_pnts[0] == current_pnts[1]:
                common_pnt = current_pnts[1]
            elif prev_pnts[1] == current_pnts[0]:
                common_pnt = current_pnts[0]
            else:
                common_pnt = current_pnts[1]
            corners.append(common_pnt)

        return corners

    @staticmethod
    def __discretize():
        Api.synchronize()
        gmsh.model.mesh.generate(2)
        # Get mesh nodes
        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        num_nodes = len(node_tags)
        node_coords_3d = list(zip(*(iter(node_coords),) * 3))  # (x, y, z) tuples

        # Build a node_id -> (x, y, z) map for later use
        node_map = dict(zip(node_tags, node_coords_3d))

        # === 2. Get all face elements (triangles & quads) ===
        surfaces = []
        # type 1 = edge, type 2 = triangle, type 15 = point
        surf_tags = Api.get_face_tags()
        for i in surf_tags:
            element_types, element_tags, node_tags_list = gmsh.model.mesh.getElements(2, i)
            faces=[]
            for elem_tags, elem_node_tags in zip(element_tags, node_tags_list):
                for i in range(len(elem_tags)):
                    elem_id = elem_tags[i]
                    node_ids = [nid - 1 for nid in elem_node_tags[i * 3: (i + 1) * 3]]
                    faces.append(node_ids)
            surfaces.append(faces)

        return node_coords_3d, surfaces
