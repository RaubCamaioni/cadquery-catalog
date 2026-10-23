import cadquery as cq


def planter(
    top_diameter: float = 100,
    bottom_diameter: float = 70,
    height: float = 90,
    wall: float = 2,
    drain_holes: int = 5,
    rim: float = 4,
) -> cq.Workplane:
    """A tapered plant pot with drainage holes and a rolled rim."""
    bottom_diameter = max(20, min(bottom_diameter, top_diameter))
    wall = max(1, min(wall, bottom_diameter / 6))
    drain_holes = max(0, min(drain_holes, 12))
    pot = cq.Workplane("XY").circle(bottom_diameter / 2).workplane(offset=height).circle(top_diameter / 2).loft()
    cavity = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .circle(bottom_diameter / 2 - wall)
        .workplane(offset=height - wall + 1)
        .circle(top_diameter / 2 - wall)
        .loft()
    )
    pot = pot.cut(cavity)
    if rim > 0:
        ring = (
            cq.Workplane("XY")
            .workplane(offset=height - rim)
            .circle(top_diameter / 2 + rim)
            .circle(top_diameter / 2 - wall)
            .extrude(rim)
        )
        pot = pot.union(ring).faces(">Z").edges().fillet(min(rim / 2.5, 1.5))
    if drain_holes:
        holes = cq.Workplane("XY").polarArray(bottom_diameter / 4, 0, 360, drain_holes).circle(3).extrude(wall)
        pot = pot.cut(holes)
    return pot
