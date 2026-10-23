import cadquery as cq


def ice_cube_tray(
    columns: int = 6,
    rows: int = 3,
    cube_size: float = 25,
    depth: float = 25,
    wall: float = 1.6,
    taper: float = 3,
) -> cq.Workplane:
    """An ice cube tray of tapered cells (also a chocolate or soap mould); print it in a food-safe
    flexible filament so the cubes pop out.
    """
    columns, rows = max(1, min(columns, 12)), max(1, min(rows, 8))
    wall = max(1, wall)
    taper = max(0, min(taper, cube_size / 3))
    width, length = columns * (cube_size + wall) + wall, rows * (cube_size + wall) + wall
    tray = cq.Workplane("XY").box(width, length, depth + wall, centered=(True, True, False)).edges("|Z").fillet(4)
    for c in range(columns):
        for r in range(rows):
            x = -width / 2 + wall + cube_size / 2 + c * (cube_size + wall)
            y = -length / 2 + wall + cube_size / 2 + r * (cube_size + wall)
            cell = (
                cq.Workplane("XY")
                .workplane(offset=wall)
                .center(x, y)
                .rect(cube_size - taper, cube_size - taper)
                .workplane(offset=depth + 1)
                .rect(cube_size + taper / depth, cube_size + taper / depth)
                .loft()
            )
            tray = tray.cut(cell)
    return tray
