import cadquery as cq


def lamp_shade(
    top_diameter: float = 80,
    bottom_diameter: float = 160,
    height: float = 140,
    sides: int = 8,
    wall: float = 1.2,
    fitting_hole: float = 40,
) -> cq.Workplane:
    """A faceted lamp shade: a polygon that widens from the fitting ring at the top to the open
    bottom, hollow with a thin wall (prints in vase mode with the top ring).
    """
    sides = max(3, min(int(sides), 24))
    wall = max(0.8, wall)
    fitting_hole = max(10, min(fitting_hole, top_diameter - 10))
    outer = (
        cq.Workplane("XY").polygon(sides, bottom_diameter).workplane(offset=height).polygon(sides, top_diameter).loft()
    )
    inner = (
        cq.Workplane("XY")
        .workplane(offset=-1)
        .polygon(sides, bottom_diameter - 2 * wall)
        .workplane(offset=height - wall + 1)
        .polygon(sides, top_diameter - 2 * wall)
        .loft()
    )
    shade = outer.cut(inner)
    return shade.cut(cq.Workplane("XY").workplane(offset=height - wall - 1).circle(fitting_hole / 2).extrude(wall + 2))
