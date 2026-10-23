import cadquery as cq


def wall_bottle_opener(
    width: float = 50,
    height: float = 80,
    thickness: float = 8,
    lip_depth: float = 14,
    cap_diameter: float = 28,
    screw_hole: float = 4.5,
) -> cq.Workplane:
    """A wall-mounted bottle opener: a plate with a protruding lip that catches the cap edge. Print
    it solid, in a tough filament, with the lip's top edge at the layer lines.
    """
    thickness = max(6, thickness)
    plate = cq.Workplane("XY").box(width, thickness, height, centered=(True, False, False)).edges("|Y").fillet(6)
    lip = (
        cq.Workplane("XY")
        .box(width, lip_depth + thickness, 8, centered=(True, False, False))
        .translate((0, 0, height * 0.55))
    )
    opener = plate.union(lip)
    # the cap pocket: a round notch in the lip so the cap seats under it
    pocket = (
        cq.Workplane("XY")
        .center(0, thickness + lip_depth)
        .circle(cap_diameter / 2)
        .extrude(8)
        .translate((0, 0, height * 0.55 - 0.1))
    )
    opener = opener.cut(pocket)
    holes = (
        cq.Workplane("XZ")
        .pushPoints([(0, height * 0.12), (0, height * 0.88)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    return opener.cut(holes)
