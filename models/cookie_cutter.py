import math
from typing import Literal
import cadquery as cq


def cookie_cutter(
    shape: Literal["circle", "star", "heart", "hexagon", "square"] = "star",
    size: float = 70,
    height: float = 15,
    blade: float = 0.8,
    rim: float = 4,
    points: int = 5,
) -> cq.Workplane:
    """A cookie cutter: a thin cutting wall around a shape, with a wider rim at the top to press on."""
    blade = max(0.6, blade)
    rim = max(blade + 1, rim)
    r = size / 2
    points = max(3, min(points, 12))

    def outline() -> cq.Workplane:
        if shape == "star":
            pts = []
            for i in range(points * 2):
                a = math.pi / 2 + i * math.pi / points
                rr = r if i % 2 == 0 else r * 0.45
                pts.append((rr * math.cos(a), rr * math.sin(a)))
            return cq.Workplane("XY").polyline(pts).close()
        if shape == "heart":
            return (
                cq.Workplane("XY")
                .moveTo(0, -r)
                .lineTo(r * 0.9, 0)
                .threePointArc((r * 0.7, r * 0.6), (r * 0.45, r * 0.45))
                .threePointArc((r * 0.2, r * 0.25), (0, r * 0.3))
                .threePointArc((-r * 0.2, r * 0.25), (-r * 0.45, r * 0.45))
                .threePointArc((-r * 0.7, r * 0.6), (-r * 0.9, 0))
                .close()
            )
        if shape == "hexagon":
            return cq.Workplane("XY").polygon(6, size)
        if shape == "square":
            return cq.Workplane("XY").rect(size, size)
        return cq.Workplane("XY").circle(r)

    inside = outline().extrude(height + 2).translate((0, 0, -1))
    wall = outline().offset2D(blade).extrude(height).cut(inside)
    top = outline().offset2D(rim).extrude(3).translate((0, 0, height - 3)).cut(inside)
    return wall.union(top)
