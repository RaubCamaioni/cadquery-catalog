import cadquery as cq


def hex_tray(
    width: float = 100,
    height: float = 20,
    wall: float = 2,
    draft_angle: float = 10,
    floor_thickness: float = 2,
) -> cq.Workplane:
    """A hexagonal catch-all dish whose sides lean outward by the draft angle."""
    import math

    draft_angle = max(0, min(draft_angle, 30))
    wall = max(0.8, min(wall, width / 10))
    top_width = width + 2 * height * math.tan(math.radians(draft_angle))
    outer = cq.Workplane("XY").polygon(6, width).workplane(offset=height).polygon(6, top_width).loft()
    inner = (
        cq.Workplane("XY")
        .workplane(offset=floor_thickness)
        .polygon(6, width - 2 * wall)
        .workplane(offset=height - floor_thickness + 1)
        .polygon(6, top_width - 2 * wall)
        .loft()
    )
    return outer.cut(inner).edges("|Z or (not |Z)").edges("not <Z").fillet(min(1, wall / 2.5))
