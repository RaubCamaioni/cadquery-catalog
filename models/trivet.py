import math
import cadquery as cq


def trivet(
    diameter: float = 160,
    thickness: float = 8,
    cell_size: float = 18,
    strut: float = 3,
    rim: float = 6,
) -> cq.Workplane:
    """A honeycomb trivet for hot pans: a rim around a hexagonal lattice."""
    cell_size = max(6, min(cell_size, diameter / 3))
    strut = max(1.2, strut)
    disc = cq.Workplane("XY").circle(diameter / 2).extrude(thickness).edges().chamfer(min(1, thickness / 5))
    pitch = cell_size + strut
    points = []
    rows = int(diameter / (pitch * 0.866)) + 2
    cols = int(diameter / pitch) + 2
    for r in range(-rows, rows + 1):
        for c in range(-cols, cols + 1):
            x = c * pitch + (pitch / 2 if r % 2 else 0)
            y = r * pitch * 0.866
            if math.hypot(x, y) + cell_size / 2 < diameter / 2 - rim:
                points.append((x, y))
    holes = cq.Workplane("XY").pushPoints(points).polygon(6, cell_size / 0.866).extrude(thickness)
    return disc.cut(holes)
