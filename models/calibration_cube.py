import cadquery as cq


def calibration_cube(
    size: float = 20,
    hole_diameter: float = 8,
    chamfer: float = 1,
) -> cq.Workplane:
    """A printer calibration cube with a through hole on each axis and chamfered edges, so
    dimensional accuracy, hole shrinkage and corner quality can all be measured on one print.
    """
    size = max(5, size)
    hole_diameter = max(0, min(hole_diameter, size * 0.6))
    cube = cq.Workplane("XY").box(size, size, size, centered=(True, True, False))
    chamfer = max(0, min(chamfer, size / 8))
    if chamfer > 0:
        cube = cube.edges().chamfer(chamfer)
    if hole_diameter > 0:
        for plane, offset in (("XY", (0, 0, 0)), ("XZ", (0, size / 2, size / 2)), ("YZ", (-size / 2, 0, size / 2))):
            cube = cube.cut(cq.Workplane(plane).circle(hole_diameter / 2).extrude(size, both=True).translate(offset))
    return cube
