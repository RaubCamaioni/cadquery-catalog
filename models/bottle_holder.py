import cadquery as cq


def bottle_holder(
    bottle_diameter: float = 75,
    ring_height: float = 25,
    wall: float = 3,
    back_width: float = 40,
    back_height: float = 70,
    screw_hole: float = 4.5,
) -> cq.Workplane:
    """A wall-mounted ring that holds a bottle or spray can by its body, with a ledge under the ring
    so the bottle cannot slide through; two screws through the back plate.
    """
    wall = max(2, wall)
    r = bottle_diameter / 2 + 0.5
    ring = cq.Workplane("XY").circle(r + wall).circle(r).extrude(ring_height)
    ledge = cq.Workplane("XY").circle(r + 0.1).circle(r - 8).extrude(wall)
    back = (
        cq.Workplane("XY")
        .box(back_width, wall + 2, back_height, centered=(True, False, False))
        .translate((0, r + wall - 2, 0))
    )
    bridge = cq.Workplane("XY").box(back_width, 6, ring_height, centered=(True, False, False)).translate((0, r - 3, 0))
    holder = ring.union(ledge).union(bridge).union(back)
    holes = (
        cq.Workplane("XZ")
        .pushPoints([(0, back_height * 0.15), (0, back_height * 0.85)])
        .circle(screw_hole / 2)
        .extrude(-(r + wall + 5))
    )
    return holder.cut(holes)
