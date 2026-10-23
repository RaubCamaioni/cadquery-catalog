import cadquery as cq


def standoff_plate(
    hole_spacing_x: float = 58,
    hole_spacing_y: float = 49,
    standoff_height: float = 6,
    standoff_diameter: float = 6,
    screw_hole: float = 2.5,
    margin: float = 6,
    plate_thickness: float = 3,
) -> cq.Workplane:
    """A mounting plate with four standoffs for a circuit board, from the board's hole pattern
    (a Raspberry Pi by default).
    """
    w, d = hole_spacing_x + 2 * margin + standoff_diameter, hole_spacing_y + 2 * margin + standoff_diameter
    plate = cq.Workplane("XY").box(w, d, plate_thickness, centered=(True, True, False)).edges("|Z").fillet(3)
    points = [(ix * hole_spacing_x / 2, iy * hole_spacing_y / 2) for ix in (-1, 1) for iy in (-1, 1)]
    posts = (
        cq.Workplane("XY")
        .workplane(offset=plate_thickness)
        .pushPoints(points)
        .circle(standoff_diameter / 2)
        .extrude(standoff_height)
    )
    holes = cq.Workplane("XY").pushPoints(points).circle(screw_hole / 2).extrude(plate_thickness + standoff_height)
    # four corner holes to fix the plate itself
    fixings = (
        cq.Workplane("XY")
        .pushPoints([(ix * (w / 2 - 4), iy * (d / 2 - 4)) for ix in (-1, 1) for iy in (-1, 1)])
        .circle(1.8)
        .extrude(plate_thickness)
    )
    return plate.union(posts).cut(holes).cut(fixings)
