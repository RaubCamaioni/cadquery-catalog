import cadquery as cq


def funnel(
    top_diameter: float = 90,
    spout_diameter: float = 12,
    cone_height: float = 60,
    spout_length: float = 30,
    wall: float = 1.6,
) -> cq.Workplane:
    """A funnel: a cone that narrows to a straight spout, hollow with a constant wall."""
    spout_diameter = max(4, min(spout_diameter, top_diameter - 10))
    wall = max(0.8, min(wall, spout_diameter / 3))
    outer = (
        cq.Workplane("XY")
        .circle(spout_diameter / 2 + wall)
        .extrude(spout_length)
        .faces(">Z")
        .workplane()
        .circle(spout_diameter / 2 + wall)
        .workplane(offset=cone_height)
        .circle(top_diameter / 2 + wall)
        .loft()
    )
    inner = (
        cq.Workplane("XY")
        .circle(spout_diameter / 2)
        .extrude(spout_length)
        .faces(">Z")
        .workplane()
        .circle(spout_diameter / 2)
        .workplane(offset=cone_height)
        .circle(top_diameter / 2)
        .loft()
    )
    # a short cylinder below and above keeps the cut clean through both ends
    through = (
        cq.Workplane("XY").circle(spout_diameter / 2).extrude(spout_length + cone_height + 2).translate((0, 0, -1))
    )
    return outer.cut(inner).cut(through)
