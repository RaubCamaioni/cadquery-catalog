import cadquery as cq


def desk_cable_clamp(
    desk_thickness: float = 25,
    clamp_depth: float = 30,
    width: float = 20,
    thickness: float = 4,
    cable_diameter: float = 7,
    cables: int = 2,
) -> cq.Workplane:
    """A clip that pushes onto the edge of a desk and holds cables in open rings on its top."""
    thickness = max(3, thickness)
    cables = max(1, min(cables, 6))
    gap = desk_thickness - 0.4  # a slight pinch
    clamp = (
        cq.Workplane("XY")
        .box(width, thickness, gap + 2 * thickness, centered=(True, False, False))
        .union(cq.Workplane("XY").box(width, clamp_depth, thickness, centered=(True, False, False)))
        .union(
            cq.Workplane("XY")
            .box(width, clamp_depth, thickness, centered=(True, False, False))
            .translate((0, 0, gap + thickness))
        )
    )
    pitch = cable_diameter + thickness
    for i in range(cables):
        y = thickness + pitch * (i + 0.5)
        ring = (
            cq.Workplane("XZ")
            .center(0, gap + 2 * thickness + cable_diameter / 2 + 1)
            .circle(cable_diameter / 2 + thickness / 2)
            .circle(cable_diameter / 2)
            .extrude(-pitch * 0.8)
            .translate((0, y - pitch * 0.4, 0))
        )
        mouth = (
            cq.Workplane("XY")
            .center(0, y)
            .rect(cable_diameter * 0.7, pitch)
            .extrude(cable_diameter + thickness + 2)
            .translate((0, 0, gap + 2 * thickness + cable_diameter / 2 + 1))
        )
        clamp = clamp.union(ring).cut(mouth)
    return clamp
