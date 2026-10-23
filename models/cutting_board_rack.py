import cadquery as cq


def cutting_board_rack(
    slots: int = 3,
    slot_width: float = 25,
    divider: float = 6,
    depth: float = 150,
    height: float = 60,
    base_thickness: float = 6,
) -> cq.Workplane:
    """An upright rack with wide slots that hold cutting boards and baking sheets on edge."""
    slots = max(1, min(slots, 8))
    length = slots * (slot_width + divider) + divider
    base = cq.Workplane("XY").box(length, depth, base_thickness, centered=(True, True, False)).edges("|Z").fillet(5)
    rack = base
    for i in range(slots + 1):
        x = -length / 2 + divider / 2 + i * (slot_width + divider)
        fin = cq.Workplane("XY").center(x, 0).rect(divider, depth - 30).extrude(height + base_thickness)
        rack = rack.union(fin)
    # feet cutouts underneath so it sits flat on uneven counters
    feet = cq.Workplane("XY").rect(length - 40, depth + 2).extrude(1.5)
    return rack.cut(feet)
