import cadquery as cq


def power_strip_cover(
    length: float = 320,
    width: float = 130,
    height: float = 110,
    wall: float = 2.4,
    cable_slot_width: float = 30,
    cable_slot_height: float = 20,
    vent_slots: int = 6,
) -> cq.Workplane:
    """An upside-down box that hides a power strip, with a cable slot at each end and vent slots on
    the sides. Printed open side down; the lid is the floor of the print.
    """
    wall = max(1.6, wall)
    box = cq.Workplane("XY").box(length, width, height, centered=(True, True, False)).edges("|Z").fillet(8)
    inner = cq.Workplane("XY").workplane(offset=-1).rect(length - 2 * wall, width - 2 * wall).extrude(height - wall + 1)
    cover = box.cut(inner)
    slots = (
        cq.Workplane("YZ")
        .pushPoints([(0, cable_slot_height / 2)])
        .rect(cable_slot_width, cable_slot_height + 2)
        .extrude(length / 2 + 1, both=True)
    )
    cover = cover.cut(slots)
    if vent_slots:
        pitch = (length - 40) / vent_slots
        pts = [(-length / 2 + 20 + pitch * (i + 0.5), height * 0.6) for i in range(vent_slots)]
        vents = cq.Workplane("XZ").pushPoints(pts).rect(pitch * 0.4, height * 0.4).extrude(width / 2 + 1, both=True)
        cover = cover.cut(vents)
    return cover
