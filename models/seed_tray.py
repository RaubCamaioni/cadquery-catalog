import cadquery as cq


def seed_tray(
    columns: int = 6,
    rows: int = 4,
    cell_size: float = 35,
    depth: float = 45,
    wall: float = 1.2,
    taper: float = 6,
    drain_hole: float = 4,
) -> cq.Workplane:
    """A seed starter tray of tapered cells with a drain hole in each, so seedlings pop out easily."""
    columns, rows = max(1, min(columns, 12)), max(1, min(rows, 12))
    wall = max(0.8, wall)
    taper = max(0, min(taper, cell_size / 3))
    width, length = columns * (cell_size + wall) + wall, rows * (cell_size + wall) + wall
    tray = cq.Workplane("XY").box(width, length, depth, centered=(True, True, False))
    pts = [
        (
            -width / 2 + wall + cell_size / 2 + c * (cell_size + wall),
            -length / 2 + wall + cell_size / 2 + r * (cell_size + wall),
        )
        for c in range(columns)
        for r in range(rows)
    ]
    for p in pts:
        cell = (
            cq.Workplane("XY")
            .workplane(offset=wall)
            .center(*p)
            .rect(cell_size - taper, cell_size - taper)
            .workplane(offset=depth - wall + 1)
            .rect(cell_size + taper * 1 / (depth - wall), cell_size + taper * 1 / (depth - wall))
            .loft()
        )
        tray = tray.cut(cell)
    drains = cq.Workplane("XY").pushPoints(pts).circle(drain_hole / 2).extrude(wall)
    return tray.cut(drains)
