import cadquery as cq


def storage_box(
    width: float = 80,
    depth: float = 60,
    height: float = 40,
    wall: float = 2.4,
    corner_radius: float = 6,
) -> cq.Workplane:
    """An open-top box with rounded vertical corners and a floor one wall thick."""
    corner_radius = min(corner_radius, min(width, depth) / 2 - wall)
    return (
        cq.Workplane("XY")
        .box(width, depth, height, centered=(True, True, False))
        .edges("|Z")
        .fillet(corner_radius)
        .faces(">Z")
        .shell(-wall)
    )
