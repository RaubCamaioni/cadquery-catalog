import cadquery as cq


def tube_squeezer(
    width: float = 50,
    slot_width: float = 2.5,
    diameter: float = 10,
    key_length: float = 15,
) -> cq.Workplane:
    """A toothpaste tube key: a rod with a slot that the tube end slides into and rolls up on."""
    diameter = max(6, diameter)
    rod = cq.Workplane("YZ").circle(diameter / 2).extrude(width / 2, both=True)
    slot = (
        cq.Workplane("XY")
        .rect(width + 2, slot_width)
        .extrude(diameter)
        .translate((0, 0, -diameter / 2))
        .translate((0, 0, diameter * 0.1))
    )
    key = (
        cq.Workplane("XY")
        .box(key_length, diameter * 1.6, diameter / 2, centered=(False, True, True))
        .translate((width / 2 - 0.5, 0, 0))
        .edges("|Z")
        .fillet(2)
    )
    return rod.cut(slot).union(key)
