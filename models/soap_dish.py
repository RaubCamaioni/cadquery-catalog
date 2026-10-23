import cadquery as cq


def soap_dish(
    length: float = 110,
    width: float = 75,
    height: float = 22,
    wall: float = 2,
    drain_slots: int = 6,
    slot_width: float = 4,
) -> cq.Workplane:
    """A soap dish with rounded corners and drain slots across the floor."""
    wall = max(1, min(wall, width / 10))
    drain_slots = max(0, min(drain_slots, 20))
    dish = (
        cq.Workplane("XY")
        .box(length, width, height, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(12, width / 4))
        .faces(">Z")
        .shell(-wall)
    )
    if drain_slots:
        pitch = (length - 20) / drain_slots
        slots = (
            cq.Workplane("XY")
            .pushPoints([(-length / 2 + 10 + pitch * (i + 0.5), 0) for i in range(drain_slots)])
            .slot2D(width - 20, slot_width, angle=90)
            .extrude(wall)
        )
        dish = dish.cut(slots)
    return dish
