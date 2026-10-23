import cadquery as cq


def shelf_bracket(
    shelf_depth: float = 150,
    wall_height: float = 150,
    width: float = 20,
    thickness: float = 8,
    screw_hole: float = 4.5,
    web_thickness: float = 4,
) -> cq.Workplane:
    """A triangular shelf bracket: a wall leg, a shelf leg and a diagonal web, with screw holes in both legs."""
    thickness = max(4, thickness)
    wall_leg = cq.Workplane("XY").box(width, thickness, wall_height, centered=(True, False, False))
    shelf_leg = (
        cq.Workplane("XY")
        .box(width, shelf_depth, thickness, centered=(True, False, False))
        .translate((0, 0, wall_height - thickness))
    )
    web = (
        cq.Workplane("YZ")
        .polyline(
            [(thickness, 0), (shelf_depth - thickness, wall_height - thickness), (thickness, wall_height - thickness)]
        )
        .close()
        .extrude(web_thickness / 2, both=True)
    )
    bracket = wall_leg.union(shelf_leg).union(web)
    wall_holes = (
        cq.Workplane("XZ")
        .pushPoints([(0, wall_height * 0.2), (0, wall_height * 0.8)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    shelf_holes = (
        cq.Workplane("XY")
        .pushPoints([(0, shelf_depth * 0.4), (0, shelf_depth * 0.85)])
        .circle(screw_hole / 2)
        .extrude(thickness + 1)
        .translate((0, 0, wall_height - thickness - 0.5))
    )
    return bracket.cut(wall_holes).cut(shelf_holes)
