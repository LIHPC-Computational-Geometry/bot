import unittest
from bot.core.cad import CADModel


class GeomTest(unittest.TestCase):
    def test_topology_query_2D(self):
        cad = CADModel()
        cad.open("data/profil_1.geo")

        # check the number of loaded points
        self.assertEqual(6, len(cad.get_point_tags()))
        # check the number of loaded curves
        self.assertEqual(5, len(cad.get_curve_tags()))
        # check the number of loaded surfaces
        self.assertEqual(0, len(cad.get_surface_tags()))
        for tag in cad.get_curve_tags():
            self.assertEqual(2, len(cad.get_end_points(tag)))

        nb_points_2 = 0
        nb_points_0 = 0
        for tag in cad.get_point_tags():
            nb_curves = len(cad.get_adjacent_curves_of_point(tag))
            self.assertTrue(nb_curves == 2 or nb_curves == 0)
            if nb_curves == 2:
                nb_points_2 += 1
            else:
                nb_points_0 += 1
        self.assertEqual(6, len(cad.get_point_tags()))
        self.assertEqual(5, nb_points_2)
        self.assertEqual(1, nb_points_0)
        cad.finalize()

    def test_raise_error_point_access(self):
        cad = CADModel()
        cad.open("data/profil_1.geo")

        # check that the function raises an exception for a point id that is not in the model
        with self.assertRaises(ValueError) as context:
            cad.get_adjacent_curves_of_point(10)

        # Check that the error message is correct,
        self.assertEqual(str(context.exception), "Invalid point tag")

    def test_closest_points(self):
        cad = CADModel()
        cad.open("data/profil_1.geo")
        # We consider two points simultaneously
        coords = [2, 0, 0, 4, 2, 0]
        # We get the closest points on the 2nd curve which is a straight line
        # that connects (0,1,0) to (5,1,0)
        outputs = cad.getClosestPoint(1, 2, coords)
        # We know what should be the closest points
        oracle = [2, 1, 0, 4, 1, 0]

        # and we compare
        epsilon = 1e-9
        for v1, v2 in zip(oracle, outputs):
            self.assertAlmostEqual(v1, v2, delta=epsilon)


if __name__ == "__main__":
    unittest.main()
