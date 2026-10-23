import cadquery as cq


def usb_stick_holder(
    slots: int = 6,
    slot_width: float = 13,
    slot_thickness: float = 5.5,
    slot_depth: float = 10,
    pitch: float = 18,
    wall: float = 2,
) -> cq.Workplane:
    """A block that holds USB sticks upright by their plugs; also fits SD cards with the slot narrowed."""
    slots = max(1, min(slots, 24))
    pitch = max(slot_width + 2, pitch)
    length = slots * pitch + wall
    body = (
        cq.Workplane("XY")
        .box(length, slot_thickness + 2 * wall + 6, slot_depth + wall, centered=(True, True, False))
        .edges("|Z")
        .fillet(2)
    )
    cuts = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .pushPoints([(-length / 2 + wall + pitch / 2 + i * pitch, 0) for i in range(slots)])
        .rect(slot_width + 0.4, slot_thickness + 0.4)
        .extrude(slot_depth + 1)
    )
    return body.cut(cuts).faces(">Z").edges().chamfer(min(0.8, wall / 3))
