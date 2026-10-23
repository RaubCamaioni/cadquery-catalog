import cadquery as cq


def key_holder(
    hooks: int = 5,
    spacing: float = 30,
    plate_height: float = 40,
    thickness: float = 4,
    hook_diameter: float = 4,
    hook_length: float = 18,
    shelf_depth: float = 0,
) -> cq.Workplane:
    """A key holder: a wall plate with a row of peg hooks and, optionally, a small shelf on top."""
    hooks = max(1, min(hooks, 12))
    width = spacing * (hooks + 1)
    plate = cq.Workplane("XY").box(width, thickness, plate_height, centered=(True, False, False)).edges("|Y").fillet(4)
    pegs = (
        cq.Workplane("XZ")
        .pushPoints([(-width / 2 + spacing * (i + 1), plate_height * 0.4) for i in range(hooks)])
        .circle(hook_diameter / 2)
        .extrude(-hook_length)
    )
    tips = (
        cq.Workplane("XZ")
        .pushPoints([(-width / 2 + spacing * (i + 1), plate_height * 0.4) for i in range(hooks)])
        .circle(hook_diameter / 2 + 1.5)
        .extrude(-hook_length)
        .cut(cq.Workplane("XZ").rect(width, plate_height * 2).extrude(-(hook_length - 3)))
    )
    holder = plate.union(pegs).union(tips)
    if shelf_depth > 0:
        shelf = (
            cq.Workplane("XY")
            .box(width, shelf_depth + thickness, thickness, centered=(True, False, False))
            .translate((0, 0, plate_height - thickness))
        )
        holder = holder.union(shelf)
    screws = (
        cq.Workplane("XZ")
        .pushPoints([(-width / 2 + spacing / 2, plate_height * 0.75), (width / 2 - spacing / 2, plate_height * 0.75)])
        .circle(2.2)
        .extrude(-thickness * 2)
    )
    return holder.cut(screws)
