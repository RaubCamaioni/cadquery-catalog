import cadquery as cq


def drawer_tray(
    width: float = 120,
    depth: float = 80,
    height: float = 30,
    columns: int = 3,
    rows: int = 2,
    wall: float = 1.6,
    corner_radius: float = 3,
) -> cq.Workplane:
    """A drawer organiser: an open tray split into a grid of equal compartments."""
    columns, rows = max(1, min(columns, 12)), max(1, min(rows, 12))
    wall = max(0.8, min(wall, min(width, depth) / 8))
    corner_radius = max(0.2, min(corner_radius, min(width, depth) / 4 - wall))
    tray = cq.Workplane("XY").box(width, depth, height, centered=(True, True, False)).edges("|Z").fillet(corner_radius)
    cell_w = (width - wall * (columns + 1)) / columns
    cell_d = (depth - wall * (rows + 1)) / rows
    points = [
        (-width / 2 + wall + cell_w / 2 + c * (cell_w + wall), -depth / 2 + wall + cell_d / 2 + r * (cell_d + wall))
        for c in range(columns)
        for r in range(rows)
    ]
    pockets = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .pushPoints(points)
        .rect(cell_w, cell_d)
        .extrude(height)
        .edges("|Z")
        .fillet(min(corner_radius, min(cell_w, cell_d) / 3))
    )
    return tray.cut(pockets)
