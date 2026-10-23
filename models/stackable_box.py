import cadquery as cq


def stackable_box(
    width: float = 100,
    depth: float = 70,
    height: float = 50,
    wall: float = 2,
    lip: float = 4,
    corner_radius: float = 5,
) -> cq.Workplane:
    """A stackable open box: a stepped lip on top that the base of the next box sits into."""
    wall = max(1, min(wall, min(width, depth) / 10))
    lip = max(1, min(lip, height / 4))
    corner_radius = max(0.5, min(corner_radius, min(width, depth) / 4))
    box = (
        cq.Workplane("XY")
        .box(width, depth, height, centered=(True, True, False))
        .edges("|Z")
        .fillet(corner_radius)
        .faces(">Z")
        .shell(-wall)
    )
    # the lip: the top `lip` of the wall is thinned to half, from the outside, so the box above nests
    step = (
        cq.Workplane("XY")
        .workplane(offset=height - lip)
        .rect(width + 1, depth + 1)
        .extrude(lip + 1)
        .cut(
            cq.Workplane("XY")
            .workplane(offset=height - lip - 1)
            .rect(width - wall, depth - wall)
            .extrude(lip + 3)
            .edges("|Z")
            .fillet(max(0.2, corner_radius - wall / 2))
        )
    )
    return box.cut(step)
