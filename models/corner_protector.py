import cadquery as cq


def corner_protector(
    size: float = 40,
    thickness: float = 4,
    board_thickness: float = 18,
    rounding: float = 8,
) -> cq.Workplane:
    """A corner guard that slips over the corner of a table or board: three faces around the corner."""
    thickness = max(1.5, thickness)
    rounding = max(0.5, min(rounding, size / 3))
    outer = size + thickness
    block = cq.Workplane("XY").box(outer, outer, board_thickness + 2 * thickness, centered=(False, False, False))
    inner = (
        cq.Workplane("XY")
        .box(size + 1, size + 1, board_thickness, centered=(False, False, False))
        .translate((thickness, thickness, thickness))
    )
    guard = block.cut(inner).edges("|Z").edges("<X and <Y").fillet(rounding)
    return guard.edges("<X or <Y").fillet(min(1.5, thickness / 2.5))
