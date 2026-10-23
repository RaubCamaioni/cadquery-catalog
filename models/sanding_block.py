import cadquery as cq


def sanding_block(
    length: float = 120,
    width: float = 65,
    height: float = 35,
    grip_radius: float = 12,
    paper_slot: float = 1.5,
) -> cq.Workplane:
    """A hand sanding block with a rounded grip and slots along both long edges to tuck the paper into."""
    block = cq.Workplane("XY").box(length, width, height, centered=(True, True, False))
    block = block.edges("|X").edges(">Z").fillet(min(grip_radius, height / 2.5))
    finger = (
        cq.Workplane("XY")
        .center(0, 0)
        .rect(length - 20, width - 24)
        .extrude(6)
        .translate((0, 0, height - 6))
        .edges("|Z")
        .fillet(6)
    )
    block = block.cut(finger)
    slots = (
        cq.Workplane("XY")
        .pushPoints([(0, -width / 2 + 3), (0, width / 2 - 3)])
        .rect(length - 10, paper_slot)
        .extrude(height * 0.45)
        .translate((0, 0, 3))
    )
    return block.cut(slots)
