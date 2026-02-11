// Gmsh project created on Wed Nov 12 08:08:39 2025
SetFactory("OpenCASCADE");
//+
Point(1) = {0, 0, 0, 1.0};
//+
Point(2) = {-1, 0, 0, 1.0};
//+
Point(3) = {0, 1, 0, 1.0};
//+
Point(4) = {5, 1, 0, 1.0};
//+
Point(5) = {8, 3, 0, 1.0};
//+
Point(6) = {8, 0, 0, 1.0};
//+
Circle(1) = {2, 1, 3};
//+
Line(2) = {3, 4};
//+
Line(3) = {4, 5};
//+
Line(4) = {5, 6};
//+
Line(5) = {6, 2};
