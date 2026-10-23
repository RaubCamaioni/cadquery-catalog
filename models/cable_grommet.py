import cadquery as cq


def cable_grommet(
    hole_diameter: float = 60,
    panel_thickness: float = 25,
    flange: float = 6,
    wall: float = 2,
    cable_opening: float = 20,
) -> cq.Workplane:
    """A desk grommet: a sleeve that drops into a hole in the desk top, with a flange and a
    notch in the sleeve for the cables to pass sideways.
    """
    wall = max(1.2, min(wall, hole_diameter / 8))
    cable_opening = max(0, min(cable_opening, hole_diameter - wall * 2 - 4))
    sleeve = (
        cq.Workplane("XY")
        .circle(hole_diameter / 2 - 0.3)
        .circle(hole_diameter / 2 - 0.3 - wall)
        .extrude(panel_thickness + 2)
    )
    top = (
        cq.Workplane("XY")
        .workplane(offset=panel_thickness + 2)
        .circle(hole_diameter / 2 + flange)
        .circle(hole_diameter / 2 - 0.3 - wall)
        .extrude(2)
        .faces(">Z")
        .edges()
        .fillet(0.8)
    )
    grommet = sleeve.union(top)
    if cable_opening > 0:
        notch = (
            cq.Workplane("XY").center(0, -hole_diameter / 2).rect(cable_opening, wall * 4).extrude(panel_thickness + 4)
        )
        grommet = grommet.cut(notch)
    return grommet
