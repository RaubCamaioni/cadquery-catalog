import cadquery as cq


def toothbrush_holder(
    slots: int = 4,
    slot_diameter: float = 22,
    height: float = 100,
    wall: float = 2,
    drain_hole: float = 6,
) -> cq.Workplane:
    """A row of tubes for toothbrushes, joined into one stand, each with a drain hole in the floor."""
    slots = max(1, min(slots, 8))
    wall = max(1.2, wall)
    pitch = slot_diameter + wall
    width = slots * pitch + wall
    body = (
        cq.Workplane("XY")
        .box(width, slot_diameter + 2 * wall, height, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(6, slot_diameter / 3))
    )
    points = [(-width / 2 + wall + slot_diameter / 2 + i * pitch, 0) for i in range(slots)]
    tubes = cq.Workplane("XY").workplane(offset=wall).pushPoints(points).circle(slot_diameter / 2).extrude(height)
    drains = cq.Workplane("XY").pushPoints(points).circle(min(drain_hole, slot_diameter - 4) / 2).extrude(wall)
    return body.cut(tubes).cut(drains).faces(">Z").edges().chamfer(min(1, wall / 2.5))
