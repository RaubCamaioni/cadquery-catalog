import cadquery as cq


def bike_wall_hook(
    tire_width: float = 55,
    hook_depth: float = 70,
    hook_height: float = 60,
    thickness: float = 10,
    back_width: float = 60,
    back_height: float = 120,
    screw_hole: float = 6,
) -> cq.Workplane:
    """A heavy wall hook that hangs a bicycle by its front wheel: a J-shaped channel the tire sits in,
    on a tall back plate with four screw holes. Print with thick walls and plenty of infill.
    """
    thickness = max(8, thickness)
    back = (
        cq.Workplane("XY").box(back_width, thickness, back_height, centered=(True, False, False)).edges("|Y").fillet(6)
    )
    arm = (
        cq.Workplane("XY")
        .box(tire_width + 2 * thickness, hook_depth, thickness, centered=(True, False, False))
        .translate((0, 0, back_height * 0.4))
    )
    lip = (
        cq.Workplane("XY")
        .box(tire_width + 2 * thickness, thickness, hook_height, centered=(True, False, False))
        .translate((0, hook_depth - thickness, back_height * 0.4))
    )
    channel = (
        cq.Workplane("XY")
        .box(tire_width, hook_depth, hook_height + 1, centered=(True, False, False))
        .translate((0, thickness, back_height * 0.4 + thickness))
    )
    brace = (
        cq.Workplane("YZ")
        .polyline([(thickness, 0), (hook_depth * 0.8, back_height * 0.4), (thickness, back_height * 0.4)])
        .close()
        .extrude(thickness / 2, both=True)
    )
    hook = back.union(arm).union(lip).cut(channel).union(brace)
    holes = (
        cq.Workplane("XZ")
        .pushPoints([(x, y) for x in (-back_width / 3, back_width / 3) for y in (back_height * 0.1, back_height * 0.9)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    return hook.cut(holes)
