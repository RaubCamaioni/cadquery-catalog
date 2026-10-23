import cadquery as cq


def washer(
    inner_diameter: float = 8.4,
    outer_diameter: float = 16,
    thickness: float = 1.6,
    count: int = 10,
    chamfer: float = 0.3,
) -> cq.Workplane:
    """A set of flat washers laid out to print together (M8 size by default: M3 is 3.2/7, M4 4.3/9,
    M5 5.3/10, M6 6.4/12, M10 10.5/20).
    """
    count = max(1, min(count, 100))
    inner_diameter = max(1, min(inner_diameter, outer_diameter - 2))
    cols = min(count, 10)
    pitch = outer_diameter + 3
    pts = [((i % cols) * pitch, (i // cols) * pitch) for i in range(count)]
    washers = (
        cq.Workplane("XY").pushPoints(pts).circle(outer_diameter / 2).circle(inner_diameter / 2).extrude(thickness)
    )
    if chamfer > 0 and chamfer < thickness / 2:
        try:
            washers = washers.faces(">Z").edges().chamfer(chamfer)
        except Exception:
            pass
    return washers
