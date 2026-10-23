import cadquery as cq


def controller_stand(
    width: float = 160,
    grip_width: float = 45,
    cradle_depth: float = 30,
    height: float = 50,
    thickness: float = 5,
    angle: float = 20,
) -> cq.Workplane:
    """A stand that cradles a game controller by its two grips, leaning back at an angle."""
    thickness = max(3, thickness)
    angle = max(0, min(angle, 45))
    grip_width = max(10, min(grip_width, width / 2 - 5))
    depth = cradle_depth + 2 * thickness
    base = cq.Workplane("XY").box(width, depth + 30, thickness, centered=(True, True, False)).edges("|Z").fillet(5)
    cradle = cq.Workplane("XY").box(width, depth, height, centered=(True, True, False))
    pockets = (
        cq.Workplane("XY")
        .workplane(offset=thickness)
        .pushPoints([(-width / 2 + thickness + grip_width / 2, 0), (width / 2 - thickness - grip_width / 2, 0)])
        .rect(grip_width, cradle_depth)
        .extrude(height)
    )
    middle = (
        cq.Workplane("XY")
        .workplane(offset=thickness + 8)
        .rect(width - 2 * (thickness + grip_width), depth + 2)
        .extrude(height)
    )
    cradle = cradle.cut(pockets).cut(middle).rotate((0, 0, 0), (1, 0, 0), -angle).translate((0, 8, thickness - 0.5))
    return base.union(cradle)
