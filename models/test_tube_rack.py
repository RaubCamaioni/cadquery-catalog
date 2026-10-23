import cadquery as cq


def test_tube_rack(
    columns: int = 6,
    rows: int = 2,
    tube_diameter: float = 16,
    pitch: float = 22,
    height: float = 70,
    base_thickness: float = 5,
    wall: float = 2,
) -> cq.Workplane:
    """A two-deck test tube rack: a top plate with holes and a base with shallow dimples, joined by
    end walls. Fits 16 mm tubes by default; set the diameter for vials or centrifuge tubes.
    """
    columns, rows = max(1, min(columns, 16)), max(1, min(rows, 6))
    pitch = max(tube_diameter + 3, pitch)
    width, depth = columns * pitch + 2 * wall, rows * pitch + 2 * wall
    pts = [
        (-width / 2 + wall + pitch * (c + 0.5), -depth / 2 + wall + pitch * (r + 0.5))
        for c in range(columns)
        for r in range(rows)
    ]
    base = cq.Workplane("XY").box(width, depth, base_thickness, centered=(True, True, False))
    dimples = (
        cq.Workplane("XY")
        .workplane(offset=base_thickness - 2)
        .pushPoints(pts)
        .circle(tube_diameter / 2 + 0.5)
        .extrude(3)
    )
    base = base.cut(dimples)
    top = cq.Workplane("XY").box(width, depth, 4, centered=(True, True, False)).translate((0, 0, height - 4))
    holes = cq.Workplane("XY").workplane(offset=height - 5).pushPoints(pts).circle(tube_diameter / 2 + 0.6).extrude(6)
    top = top.cut(holes)
    ends = (
        cq.Workplane("XY")
        .pushPoints([(-width / 2 + wall / 2, 0), (width / 2 - wall / 2, 0)])
        .rect(wall, depth)
        .extrude(height)
    )
    return base.union(top).union(ends)
