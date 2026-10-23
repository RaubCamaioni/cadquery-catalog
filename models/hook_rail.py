import cadquery as cq


def hook_rail(
    hooks: int = 4,
    spacing: float = 50,
    hook_reach: float = 25,
    hook_rise: float = 12,
    thickness: float = 5,
    plate_height: float = 30,
    screw_hole: float = 4,
) -> cq.Workplane:
    """A wall rail with a row of hooks for keys, coats or cables, and screw holes at both ends."""
    hooks = max(1, min(hooks, 12))
    length = (hooks + 1) * spacing
    plate = cq.Workplane("XY").box(length, thickness, plate_height, centered=(True, False, False)).edges("|Y").fillet(3)
    rail = plate
    for i in range(hooks):
        x = -length / 2 + spacing * (i + 1)
        arm = (
            cq.Workplane("XY")
            .box(thickness * 2, hook_reach, thickness, centered=(True, False, False))
            .translate((x, 0, 4))
        )
        tip = (
            cq.Workplane("XY")
            .box(thickness * 2, thickness, hook_rise + thickness, centered=(True, False, False))
            .translate((x, hook_reach - thickness, 4))
        )
        rail = rail.union(arm).union(tip)
    holes = (
        cq.Workplane("XZ")
        .pushPoints([(-length / 2 + spacing / 2, plate_height * 0.65), (length / 2 - spacing / 2, plate_height * 0.65)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    return rail.cut(holes)
