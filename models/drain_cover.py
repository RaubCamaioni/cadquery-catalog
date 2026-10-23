import math
import cadquery as cq


def drain_cover(
    diameter: float = 90,
    thickness: float = 3,
    rim: float = 6,
    hole_diameter: float = 4,
    hole_pitch: float = 7,
    dome: float = 6,
) -> cq.Workplane:
    """A drain strainer: a perforated disc with a raised dome so hair and debris collect at the rim."""
    thickness = max(1.6, thickness)
    r = diameter / 2
    disc = cq.Workplane("XY").circle(r).extrude(thickness)
    if dome > 0:
        inner = r - rim
        cap = (
            cq.Workplane("XY")
            .workplane(offset=thickness)
            .circle(inner)
            .workplane(offset=dome)
            .circle(inner * 0.5)
            .loft()
        )
        disc = disc.union(cap)
        hollow = (
            cq.Workplane("XY")
            .workplane(offset=thickness)
            .circle(inner - thickness)
            .workplane(offset=dome - thickness)
            .circle(max(1, inner * 0.5 - thickness))
            .loft()
        )
        disc = disc.cut(hollow)
    points = []
    rows = int(diameter / hole_pitch) + 2
    for i in range(-rows, rows + 1):
        for j in range(-rows, rows + 1):
            x = i * hole_pitch + (hole_pitch / 2 if j % 2 else 0)
            y = j * hole_pitch * 0.866
            if math.hypot(x, y) < r - rim - hole_diameter:
                points.append((x, y))
    holes = cq.Workplane("XY").pushPoints(points).circle(hole_diameter / 2).extrude(thickness + dome + 1)
    return disc.cut(holes)
