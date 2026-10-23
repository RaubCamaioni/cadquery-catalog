import cadquery as cq


def blank_wall_plate(
    width: float = 70,
    height: float = 115,
    thickness: float = 3,
    screw_spacing: float = 83.3,
    screw_hole: float = 3.5,
    corner_radius: float = 6,
) -> cq.Workplane:
    """A blank cover plate for an unused switch or socket box, with countersunk screw holes
    (83.3 mm spacing fits a US single-gang box; 60.3 mm fits a European box).
    """
    thickness = max(2, thickness)
    plate = (
        cq.Workplane("XY").box(width, height, thickness, centered=(True, True, False)).edges("|Z").fillet(corner_radius)
    )
    plate = plate.faces(">Z").edges().chamfer(min(1.2, thickness / 2.5))
    pts = [(0, screw_spacing / 2), (0, -screw_spacing / 2)]
    holes = cq.Workplane("XY").pushPoints(pts).circle(screw_hole / 2).extrude(thickness)
    plate = plate.cut(holes)
    for p in pts:
        sink = (
            cq.Workplane("XY")
            .workplane(offset=thickness - screw_hole / 2)
            .center(*p)
            .circle(screw_hole / 2)
            .workplane(offset=screw_hole / 2 + 0.01)
            .circle(screw_hole)
            .loft()
        )
        plate = plate.cut(sink)
    return plate
