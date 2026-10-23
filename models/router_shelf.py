import cadquery as cq


def router_shelf(
    width: float = 200,
    depth: float = 120,
    thickness: float = 5,
    back_height: float = 60,
    screw_hole: float = 5,
    strap_slots: int = 2,
    vent_holes: int = 1,
) -> cq.Workplane:
    """A wall shelf for a router or power brick: a back plate with screw holes, a shelf with slots
    for hook-and-loop straps, vent holes, and a brace at each end.
    """
    thickness = max(4, thickness)
    back = cq.Workplane("XY").box(width, thickness, back_height, centered=(True, False, False)).edges("|Y").fillet(5)
    shelf = cq.Workplane("XY").box(width, depth, thickness, centered=(True, False, False)).edges("|Z").fillet(5)
    brace = (
        cq.Workplane("YZ")
        .polyline([(thickness, 0), (depth * 0.6, 0), (thickness, back_height * 0.7)])
        .close()
        .extrude(thickness / 2, both=True)
    )
    unit = back.union(shelf)
    unit = unit.union(brace.translate((-width / 2 + thickness / 2 + 5, 0, 0)))
    unit = unit.union(brace.translate((width / 2 - thickness / 2 - 5, 0, 0)))
    holes = (
        cq.Workplane("XZ")
        .pushPoints([(-width / 3, back_height * 0.7), (width / 3, back_height * 0.7)])
        .circle(screw_hole / 2)
        .extrude(-thickness * 2)
    )
    unit = unit.cut(holes)
    if strap_slots:
        pitch = width / (strap_slots + 1)
        pts = [(-width / 2 + pitch * (i + 1), y) for i in range(strap_slots) for y in (depth * 0.25, depth * 0.75)]
        unit = unit.cut(cq.Workplane("XY").pushPoints(pts).rect(25, 4).extrude(thickness))
    if vent_holes:
        pts = [
            (x, y)
            for x in range(int(-width / 2 + 20), int(width / 2 - 15), 12)
            for y in range(int(depth * 0.35), int(depth * 0.65), 12)
        ]
        unit = unit.cut(cq.Workplane("XY").pushPoints(pts).circle(3).extrude(thickness))
    return unit
