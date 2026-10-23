import cadquery as cq


def cable_comb(
    cables: int = 24,
    rows: int = 2,
    cable_diameter: float = 3.6,
    pitch: float = 4.2,
    thickness: float = 4,
    frame: float = 2,
) -> cq.Workplane:
    """A cable comb for sleeved PC cables: a frame with rows of holes, each opening to the row above
    through a slot narrower than the cable so cables press in and stay.
    """
    rows = max(1, min(rows, 4))
    per_row = max(1, -(-cables // rows))
    pitch = max(cable_diameter + 0.4, pitch)
    width = per_row * pitch + frame
    height = rows * pitch + frame
    comb = cq.Workplane("XY").box(width, height, thickness, centered=(True, True, False)).edges("|Z").fillet(1.5)
    for r in range(rows):
        y = -height / 2 + frame / 2 + pitch * (r + 0.5)
        xs = [-width / 2 + frame / 2 + pitch * (c + 0.5) for c in range(per_row)]
        holes = cq.Workplane("XY").pushPoints([(x, y) for x in xs]).circle(cable_diameter / 2).extrude(thickness)
        mouths = (
            cq.Workplane("XY")
            .pushPoints([(x, y + pitch / 2) for x in xs])
            .rect(cable_diameter * 0.7, pitch)
            .extrude(thickness)
        )
        comb = comb.cut(holes).cut(mouths)
    return comb
