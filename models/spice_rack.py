import cadquery as cq


def spice_rack(
    jars_per_tier: int = 5,
    tiers: int = 3,
    jar_diameter: float = 45,
    step_height: float = 30,
    step_depth: float = 50,
    wall: float = 2,
) -> cq.Workplane:
    """A stepped spice rack: each tier sits higher and further back so every jar label shows. Each
    step has shallow round pockets so the jars cannot slide.
    """
    jars_per_tier, tiers = max(1, min(jars_per_tier, 12)), max(1, min(tiers, 6))
    width = jars_per_tier * (jar_diameter + wall) + wall
    rack = None
    for t in range(tiers):
        y0 = t * step_depth
        h = (t + 1) * step_height
        step = cq.Workplane("XY").box(width, step_depth, h, centered=(True, False, False)).translate((0, y0, 0))
        pts = [
            (-width / 2 + wall + jar_diameter / 2 + i * (jar_diameter + wall), y0 + step_depth / 2)
            for i in range(jars_per_tier)
        ]
        pockets = cq.Workplane("XY").workplane(offset=h - 3).pushPoints(pts).circle(jar_diameter / 2 + 0.5).extrude(4)
        step = step.cut(pockets)
        rack = step if rack is None else rack.union(step)
    return rack
