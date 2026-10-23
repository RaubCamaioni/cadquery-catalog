import cadquery as cq


def tool_rack(
    slots: int = 6,
    slot_width: float = 12,
    slot_depth: float = 30,
    pitch: float = 28,
    height: float = 40,
    base_depth: float = 50,
    wall: float = 3,
) -> cq.Workplane:
    """A bench rack with open-front slots that hold pliers, wrenches and screwdrivers upright."""
    slots = max(1, min(slots, 20))
    pitch = max(slot_width + 4, pitch)
    length = slots * pitch + wall
    block = cq.Workplane("XY").box(length, base_depth, height, centered=(True, False, False)).edges("|Z").fillet(3)
    cuts = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .pushPoints(
            [(-length / 2 + wall + pitch / 2 + i * pitch, base_depth - slot_depth / 2 + 1) for i in range(slots)]
        )
        .rect(slot_width, slot_depth + 2)
        .extrude(height)
    )
    return block.cut(cuts).faces(">Z").edges().chamfer(min(1, wall / 3))
