import cadquery as cq


def pot_lid_rack(
    slots: int = 5,
    slot_width: float = 18,
    pitch: float = 35,
    depth: float = 120,
    height: float = 40,
    thickness: float = 3,
) -> cq.Workplane:
    """A rack of slanted slots that holds pot lids on edge, for a cabinet shelf or counter."""
    slots = max(1, min(slots, 12))
    pitch = max(slot_width + 6, pitch)
    length = slots * pitch + 10
    base = cq.Workplane("XY").box(length, depth, thickness, centered=(True, True, False)).edges("|Z").fillet(4)
    rack = base
    for i in range(slots + 1):
        x = -length / 2 + 5 + i * pitch
        fin = (
            cq.Workplane("XY")
            .box(pitch - slot_width, depth - 20, height + thickness + 8, centered=(False, True, False))
            .translate((x, 0, -8))
        )
        fin = fin.rotate((x, 0, -8), (x, 1, -8), -12)
        rack = rack.union(fin)
    return rack.intersect(cq.Workplane("XY").box(length, depth, height + thickness + 20, centered=(True, True, False)))
