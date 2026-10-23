import cadquery as cq


def pi_mount_plate(
    hole_x: float = 58,
    hole_y: float = 49,
    margin: float = 6,
    thickness: float = 3,
    standoff_height: float = 5,
    standoff_diameter: float = 6,
    screw_hole: float = 2.5,
    wall_holes: int = 1,
) -> cq.Workplane:
    """A mounting plate with four standoffs on the Raspberry Pi hole pattern (58 x 49 mm for Pi 3,
    4 and 5; set 23 x 58 for a Pi Zero) and optional wall screw holes.
    """
    w, d = hole_x + 2 * margin + standoff_diameter, hole_y + 2 * margin + standoff_diameter
    plate = cq.Workplane("XY").box(w, d, thickness, centered=(True, True, False)).edges("|Z").fillet(4)
    pts = [(x, y) for x in (-hole_x / 2, hole_x / 2) for y in (-hole_y / 2, hole_y / 2)]
    posts = (
        cq.Workplane("XY")
        .workplane(offset=thickness)
        .pushPoints(pts)
        .circle(standoff_diameter / 2)
        .extrude(standoff_height)
    )
    holes = cq.Workplane("XY").pushPoints(pts).circle(screw_hole / 2 * 0.9).extrude(thickness + standoff_height)
    plate = plate.union(posts).cut(holes)
    if wall_holes:
        plate = plate.cut(
            cq.Workplane("XY")
            .pushPoints([(0, d / 2 - margin / 2), (0, -d / 2 + margin / 2)])
            .circle(2)
            .extrude(thickness)
        )
    # a large window under the board saves material and lets air through
    plate = plate.cut(cq.Workplane("XY").rect(hole_x - 16, hole_y - 16).extrude(thickness).edges("|Z").fillet(4))
    return plate
