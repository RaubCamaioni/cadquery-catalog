import cadquery as cq


def drawer_handle(
    hole_spacing: float = 96,
    grip_width: float = 12,
    grip_height: float = 10,
    standoff: float = 25,
    screw_hole: float = 4,
    corner_radius: float = 4,
) -> cq.Workplane:
    """A bar pull for drawers and cabinet doors, built around the standard screw hole spacing."""
    length = hole_spacing + grip_width * 2
    bar = (
        cq.Workplane("XY")
        .box(length, grip_width, grip_height, centered=(True, True, False))
        .translate((0, 0, standoff))
        .edges("|Y")
        .fillet(min(corner_radius, grip_height / 2.5))
    )
    legs = (
        cq.Workplane("XY")
        .pushPoints([(-hole_spacing / 2, 0), (hole_spacing / 2, 0)])
        .rect(grip_width, grip_width)
        .extrude(standoff + 1)
    )
    holes = (
        cq.Workplane("XY")
        .pushPoints([(-hole_spacing / 2, 0), (hole_spacing / 2, 0)])
        .circle(screw_hole / 2)
        .extrude(standoff - 2)
    )
    return bar.union(legs).cut(holes)
