import cadquery as cq


def wall_hook(
    width: float = 20,
    plate_height: float = 60,
    reach: float = 35,
    thickness: float = 6,
    tip_height: float = 14,
    screw_hole: float = 4,
) -> cq.Workplane:
    """A wall hook: a screw plate, an arm that reaches out and a tip that turns up."""
    thickness = max(3, thickness)
    reach = max(thickness * 2, reach)
    plate = cq.Workplane("XY").box(width, thickness, plate_height, centered=(True, False, False))
    arm = cq.Workplane("XY").box(width, reach, thickness, centered=(True, False, False)).translate((0, 0, 0))
    tip = (
        cq.Workplane("XY")
        .box(width, thickness, tip_height + thickness, centered=(True, False, False))
        .translate((0, reach - thickness, 0))
    )
    hook = plate.union(arm).union(tip)
    holes = (
        cq.Workplane("XZ")
        .pushPoints([(0, plate_height * 0.3 + thickness), (0, plate_height * 0.8)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    return hook.cut(holes).edges("|X").fillet(min(2, thickness / 3))
