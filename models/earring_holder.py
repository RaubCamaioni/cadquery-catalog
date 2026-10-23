import cadquery as cq


def earring_holder(
    width: float = 120,
    height: float = 150,
    thickness: float = 2.4,
    hole_pitch: float = 10,
    hole_diameter: float = 2.5,
    base_depth: float = 50,
) -> cq.Workplane:
    """An earring stand: a leaning perforated plate on a base; hook earrings hang through the holes."""
    thickness = max(1.6, thickness)
    plate = cq.Workplane("XY").box(width, thickness, height, centered=(True, False, False)).edges("|Y").fillet(4)
    cols = max(1, int((width - 20) / hole_pitch))
    rows = max(1, int((height - 30) / hole_pitch))
    pts = [
        (-(cols - 1) / 2 * hole_pitch + c * hole_pitch, 20 + r * hole_pitch) for c in range(cols) for r in range(rows)
    ]
    holes = cq.Workplane("XZ").pushPoints(pts).circle(hole_diameter / 2).extrude(-thickness * 2)
    plate = plate.cut(holes).rotate((0, 0, 0), (1, 0, 0), -15)
    base = cq.Workplane("XY").box(width, base_depth, thickness + 2, centered=(True, True, False)).edges("|Z").fillet(4)
    return base.union(plate.translate((0, -base_depth / 4, thickness + 1)))
