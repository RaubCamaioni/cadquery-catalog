import cadquery as cq


def headphone_hook(
    desk_thickness: float = 25,
    clamp_depth: float = 40,
    arm_length: float = 60,
    width: float = 25,
    thickness: float = 5,
    saddle_radius: float = 18,
) -> cq.Workplane:
    """A headphone hanger that clamps onto the edge of a desk, with a curved saddle for the headband."""
    thickness = max(3, thickness)
    gap = desk_thickness + 0.5
    # C clamp: top plate, back, bottom plate
    top = (
        cq.Workplane("XY")
        .box(width, clamp_depth, thickness, centered=(True, False, False))
        .translate((0, 0, gap + thickness))
    )
    back = cq.Workplane("XY").box(width, thickness, gap + 2 * thickness, centered=(True, False, False))
    bottom = cq.Workplane("XY").box(width, clamp_depth, thickness, centered=(True, False, False))
    clamp = top.union(back).union(bottom)
    # the arm continues from the top plate away from the desk, ending in a saddle
    arm = (
        cq.Workplane("XY")
        .box(width, arm_length, thickness, centered=(True, False, False))
        .translate((0, -arm_length, gap + thickness))
    )
    saddle = (
        cq.Workplane("XY")
        .center(0, -arm_length)
        .circle(saddle_radius + thickness)
        .circle(saddle_radius)
        .extrude(thickness)
        .translate((0, 0, gap + thickness))
        .cut(
            cq.Workplane("XY")
            .center(0, -arm_length + saddle_radius)
            .rect(saddle_radius * 3, saddle_radius * 2)
            .extrude(gap + 2 * thickness)
        )
    )
    return clamp.union(arm).union(saddle)
