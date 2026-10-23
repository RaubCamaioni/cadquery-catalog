import cadquery as cq


def hose_hanger(
    width: float = 200,
    depth: float = 120,
    thickness: float = 12,
    lip_height: float = 30,
    back_height: float = 150,
    screw_hole: float = 6,
) -> cq.Workplane:
    """A wall hanger for a garden hose: a wide curved saddle so the hose does not kink, with a
    lip at the front and a tall back plate for three screws.
    """
    thickness = max(8, thickness)
    back = cq.Workplane("XY").box(width, thickness, back_height, centered=(True, False, False)).edges("|Y").fillet(8)
    saddle = (
        cq.Workplane("XY")
        .box(width, depth, thickness, centered=(True, False, False))
        .translate((0, 0, back_height * 0.3))
    )
    # a convex top so the hose coils over a curve rather than an edge
    dome = (
        cq.Workplane("YZ")
        .center(depth / 2, back_height * 0.3 + thickness)
        .ellipse(depth / 2, 25)
        .extrude(width / 2, both=True)
    )
    dome = dome.cut(
        cq.Workplane("XY")
        .box(width + 2, depth + 2, back_height * 0.3 + thickness, centered=(True, False, False))
        .translate((0, -1, 0))
    )
    lip = (
        cq.Workplane("XY")
        .box(width, thickness, lip_height + 25, centered=(True, False, False))
        .translate((0, depth - thickness, back_height * 0.3 + thickness - 0.5))
    )
    brace = (
        cq.Workplane("YZ")
        .polyline([(thickness, 0), (depth * 0.7, back_height * 0.3), (thickness, back_height * 0.3)])
        .close()
        .extrude(thickness / 2, both=True)
    )
    hanger = back.union(saddle).union(dome).union(lip)
    hanger = hanger.union(brace.translate((-width / 2 + thickness, 0, 0))).union(
        brace.translate((width / 2 - thickness, 0, 0))
    )
    holes = (
        cq.Workplane("XZ")
        .pushPoints([(-width / 3, back_height * 0.85), (width / 3, back_height * 0.85), (0, back_height * 0.1)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    return hanger.cut(holes)
