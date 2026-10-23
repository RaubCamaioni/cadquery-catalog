import cadquery as cq


def broom_holder(
    handle_diameter: float = 24,
    wall: float = 3,
    width: float = 25,
    back_width: float = 45,
    screw_hole: float = 4.5,
    opening: float = 0.8,
) -> cq.Workplane:
    """A spring clip for a broom or mop handle: the handle snaps into a C-shaped ring whose opening
    is a fraction of the handle diameter.
    """
    r = handle_diameter / 2 + 0.3
    opening = max(0.6, min(opening, 0.95))
    ring = cq.Workplane("XY").circle(r + wall).circle(r).extrude(width)
    mouth = cq.Workplane("XY").center(-r, 0).rect(2 * r + 2 * wall, handle_diameter * opening).extrude(width)
    clip = ring.cut(mouth)
    back = (
        cq.Workplane("XY")
        .box(wall + 1, back_width, width, centered=(False, True, False))
        .translate((r + wall - 1, 0, 0))
    )
    clip = clip.union(back)
    holes = (
        cq.Workplane("YZ")
        .pushPoints([(-back_width / 2 + 6, width / 2), (back_width / 2 - 6, width / 2)])
        .circle(screw_hole / 2)
        .extrude(r + wall + 5)
    )
    return clip.cut(holes)
