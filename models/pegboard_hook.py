import cadquery as cq


def pegboard_hook(
    hook_length: float = 40,
    peg_diameter: float = 6,
    hole_spacing: float = 25.4,
    hole_diameter: float = 6.35,
    plate_thickness: float = 4,
    tip_height: float = 8,
) -> cq.Workplane:
    """A pegboard hook with two pegs matching the board's hole spacing, a flat plate and a turned-up tip."""
    peg_diameter = max(3, min(peg_diameter, hole_diameter - 0.3))
    width = peg_diameter + 6
    plate = cq.Workplane("XY").box(width, plate_thickness, hole_spacing + width, centered=(True, False, False))
    pegs = (
        cq.Workplane("XZ")
        .pushPoints([(0, width / 2), (0, width / 2 + hole_spacing)])
        .circle(peg_diameter / 2)
        .extrude(plate_thickness + 6)  # XZ normal points -Y: pegs go behind the plate
    )
    arm = (
        cq.Workplane("XY")
        .box(width, hook_length + plate_thickness, peg_diameter, centered=(True, False, False))
        .translate((0, 0, width / 2 + hole_spacing - peg_diameter / 2))
    )
    tip = (
        cq.Workplane("XY")
        .box(width, peg_diameter, tip_height + peg_diameter, centered=(True, False, False))
        .translate((0, hook_length + plate_thickness - peg_diameter, width / 2 + hole_spacing - peg_diameter / 2))
    )
    return plate.union(pegs).union(arm).union(tip)
