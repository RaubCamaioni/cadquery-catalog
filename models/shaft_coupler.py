import cadquery as cq


def shaft_coupler(
    bore_a: float = 5,
    bore_b: float = 8,
    outer_diameter: float = 20,
    length: float = 30,
    set_screw: float = 3,
) -> cq.Workplane:
    """A rigid coupler joining two shafts of different diameters, with a set-screw hole for each."""
    outer_diameter = max(max(bore_a, bore_b) + 6, outer_diameter)
    body = cq.Workplane("XY").circle(outer_diameter / 2).extrude(length).faces(">Z or <Z").chamfer(1)
    hole_a = cq.Workplane("XY").circle(bore_a / 2 + 0.1).extrude(length / 2 + 0.5)
    hole_b = cq.Workplane("XY").workplane(offset=length / 2 - 0.5).circle(bore_b / 2 + 0.1).extrude(length / 2 + 1)
    coupler = body.cut(hole_a).cut(hole_b)
    if set_screw > 0:
        screws = (
            cq.Workplane("YZ")
            .pushPoints([(0, length / 4), (0, 3 * length / 4)])
            .circle(set_screw / 2)
            .extrude(outer_diameter)
        )
        coupler = coupler.cut(screws)
    return coupler
