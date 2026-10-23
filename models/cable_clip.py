import cadquery as cq


def cable_clip(
    cable_diameter: float = 6,
    slots: int = 3,
    wall: float = 2.5,
    height: float = 12,
    screw_hole: float = 3.5,
) -> cq.Workplane:
    """A screw-down cable clip: a row of C-shaped slots sized to the cable, with a mounting hole."""
    slots = max(1, min(slots, 8))
    pitch = cable_diameter + wall
    length = slots * pitch + wall + 12
    body = cq.Workplane("XY").box(length, cable_diameter + wall * 2, height, centered=(True, True, False))
    start = -length / 2 + 6 + wall + pitch / 2
    channels = (
        cq.Workplane("XY")
        .pushPoints([(start + i * pitch, wall * 0.6) for i in range(slots)])
        .circle(cable_diameter / 2)
        .extrude(height)
    )
    openings = (
        cq.Workplane("XY")
        .pushPoints([(start + i * pitch, cable_diameter / 2 + wall) for i in range(slots)])
        .rect(cable_diameter * 0.7, cable_diameter + wall)
        .extrude(height)
    )
    hole = cq.Workplane("XY").center(-length / 2 + 6, 0).circle(screw_hole / 2).extrude(height)
    return body.cut(channels).cut(openings).cut(hole).edges("|Z").fillet(1)
