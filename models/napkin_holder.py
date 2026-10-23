import cadquery as cq


def napkin_holder(
    width: float = 170,
    slot_width: float = 30,
    height: float = 90,
    wall: float = 3,
    cutout_diameter: float = 60,
) -> cq.Workplane:
    """An upright napkin holder: a base with two walls and a round cutout in each wall for fingers."""
    wall = max(2, wall)
    base = (
        cq.Workplane("XY").box(width, slot_width + 2 * wall, wall, centered=(True, True, False)).edges("|Z").fillet(4)
    )
    walls = (
        cq.Workplane("XY")
        .pushPoints([(0, -slot_width / 2 - wall / 2), (0, slot_width / 2 + wall / 2)])
        .rect(width, wall)
        .extrude(height)
        .edges("|Y")
        .fillet(min(8, width / 8))
    )
    cutouts = (
        cq.Workplane("XZ").center(0, height).circle(min(cutout_diameter, width - 20) / 2).extrude(slot_width, both=True)
    )
    return base.union(walls).cut(cutouts)
