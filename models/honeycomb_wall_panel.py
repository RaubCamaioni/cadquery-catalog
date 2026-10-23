import math
import cadquery as cq


def honeycomb_wall_panel(
    columns: int = 6,
    rows: int = 5,
    thickness: float = 8,
    cell_across_flats: float = 20,
    strut: float = 2,
    screw_holes: int = 1,
) -> cq.Workplane:
    """A Honeycomb Storage Wall compatible panel: pointy-top hexagonal holes 20 mm across flats on
    a 22 mm pitch, 8 mm thick, so standard HSW accessories clip into it.
    """
    columns, rows = max(1, min(columns, 20)), max(1, min(rows, 20))
    strut = max(1, strut)
    pitch = cell_across_flats + strut
    circ_r = cell_across_flats / 2 / math.cos(math.radians(30))  # centre to corner
    dx = pitch
    dy = pitch * math.sqrt(3) / 2
    width = columns * dx + dx / 2 + strut
    height = (rows - 1) * dy + 2 * circ_r + 2 * strut
    panel = cq.Workplane("XY").box(width, height, thickness, centered=(False, False, False))
    points = []
    for r in range(rows):
        for c in range(columns):
            x = strut + cell_across_flats / 2 + c * dx + (dx / 2 if r % 2 else 0)
            y = strut + circ_r + r * dy
            points.append((x, y))
    hexes = cq.Sketch().push(points).regularPolygon(circ_r, 6)
    panel = panel.cut(cq.Workplane("XY").placeSketch(hexes).extrude(thickness))
    if screw_holes:
        corners = [
            (strut + 4, strut + 4),
            (width - strut - 4, strut + 4),
            (strut + 4, height - strut - 4),
            (width - strut - 4, height - strut - 4),
        ]
        panel = panel.cut(cq.Workplane("XY").pushPoints(corners).circle(2.2).extrude(thickness))
    return panel
