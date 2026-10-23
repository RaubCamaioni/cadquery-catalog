import cadquery as cq


def cup_holder_insert(
    holder_diameter: float = 75,
    cup_diameter: float = 60,
    height: float = 60,
    wall: float = 2,
    drain_holes: int = 4,
) -> cq.Workplane:
    """An adapter that drops into a wide cup holder and holds a narrower cup or bottle centred."""
    cup_diameter = max(20, min(cup_diameter, holder_diameter - 2 * wall - 2))
    wall = max(1.2, wall)
    outer = cq.Workplane("XY").circle(holder_diameter / 2 - 0.5).extrude(height)
    inner = cq.Workplane("XY").workplane(offset=wall).circle(cup_diameter / 2).extrude(height)
    insert = outer.cut(inner)
    # hollow ring between the two walls to save material, closed at the bottom
    ring = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .circle(holder_diameter / 2 - 0.5 - wall)
        .circle(cup_diameter / 2 + wall)
        .extrude(height)
    )
    if holder_diameter / 2 - 0.5 - wall > cup_diameter / 2 + wall + 1:
        insert = insert.cut(ring)
    if drain_holes:
        holes = (
            cq.Workplane("XY").polarArray(cup_diameter / 4, 0, 360, max(1, min(drain_holes, 8))).circle(2).extrude(wall)
        )
        insert = insert.cut(holes)
    return insert.faces(">Z").edges().chamfer(min(0.8, wall / 3))
