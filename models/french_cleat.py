import cadquery as cq


def french_cleat(
    width: float = 100,
    height: float = 30,
    thickness: float = 12,
    angle: float = 45,
    screw_holes: int = 2,
    screw_hole: float = 4.5,
) -> cq.Workplane:
    """A French cleat pair: two mirrored wedges, one for the wall and one for the object, shown
    side by side. Both halves have screw holes.
    """
    import math

    angle = max(30, min(angle, 60))
    screw_holes = max(0, min(screw_holes, 6))
    run = thickness / math.tan(math.radians(angle))
    wedge = (
        cq.Workplane("YZ")
        .polyline([(0, 0), (thickness, 0), (thickness, height - run), (0, height)])
        .close()
        .extrude(width / 2, both=True)
    )
    if screw_holes:
        pitch = width / (screw_holes + 1)
        holes = (
            cq.Workplane("XZ")
            .pushPoints([(-width / 2 + pitch * (i + 1), height * 0.35) for i in range(screw_holes)])
            .circle(screw_hole / 2)
            .extrude(-thickness * 2)
        )
        wedge = wedge.cut(holes)
    other = wedge.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, thickness + 10, height))
    return wedge.union(other.translate((width + 10, 0, 0)))
