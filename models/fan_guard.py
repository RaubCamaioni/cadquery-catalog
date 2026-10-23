import cadquery as cq


def fan_guard(
    fan_size: float = 120,
    hole_spacing: float = 105,
    screw_hole: float = 4.4,
    thickness: float = 3,
    rings: int = 4,
    spokes: int = 5,
    bar_width: float = 2.4,
) -> cq.Workplane:
    """A finger guard for a case fan: concentric rings joined by spokes, with the fan's four mounting
    holes in the corners (120 mm fans use 105 mm spacing, 80 mm fans 71.5 mm, 92 mm fans 82.5 mm).
    """
    rings = max(1, min(rings, 10))
    spokes = max(3, min(spokes, 12))
    r_out = fan_size / 2 - 1
    plate = cq.Workplane("XY").rect(fan_size, fan_size).extrude(thickness).edges("|Z").fillet(6)
    opening = cq.Workplane("XY").circle(r_out).extrude(thickness)
    guard = plate.cut(opening)
    for i in range(1, rings + 1):
        r = r_out * i / (rings + 1)
        guard = guard.union(cq.Workplane("XY").circle(r + bar_width / 2).circle(r - bar_width / 2).extrude(thickness))
    hub = cq.Workplane("XY").circle(max(bar_width * 2, r_out / (rings + 1) / 2)).extrude(thickness)
    guard = guard.union(hub)
    for i in range(spokes):
        a = 360 * i / spokes
        spoke = (
            cq.Workplane("XY")
            .center(r_out / 2, 0)
            .rect(r_out, bar_width)
            .extrude(thickness)
            .rotate((0, 0, 0), (0, 0, 1), a)
        )
        guard = guard.union(spoke)
    s = hole_spacing / 2
    holes = (
        cq.Workplane("XY").pushPoints([(s, s), (-s, s), (s, -s), (-s, -s)]).circle(screw_hole / 2).extrude(thickness)
    )
    return guard.cut(holes)
