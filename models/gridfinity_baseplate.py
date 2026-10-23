import cadquery as cq

GRID = 42.0


def gridfinity_baseplate(
    units_x: int = 4,
    units_y: int = 3,
    thickness: float = 5,
    magnet_holes: int = 0,
    magnet_diameter: float = 6.2,
) -> cq.Workplane:
    """A Gridfinity-compatible baseplate: a grid of 42 mm sockets with the chamfered profile the bins
    sit in, optionally with magnet pockets under each socket corner.
    """
    units_x, units_y = max(1, min(units_x, 12)), max(1, min(units_y, 12))
    thickness = max(4, thickness)
    plate = cq.Workplane("XY").box(units_x * GRID, units_y * GRID, thickness, centered=(True, True, False))
    sockets = None
    corners = []
    for ix in range(units_x):
        for iy in range(units_y):
            cx, cy = (ix - (units_x - 1) / 2) * GRID, (iy - (units_y - 1) / 2) * GRID
            socket = (
                cq.Workplane("XY")
                .workplane(offset=thickness)
                .center(cx, cy)
                .rect(GRID - 0.3, GRID - 0.3)
                .extrude(-4.65)
                .edges("|Z")
                .fillet(4.0)
                .faces("<Z")
                .chamfer(2.7)
            )
            sockets = socket if sockets is None else sockets.union(socket)
            corners += [(cx + dx * 13, cy + dy * 13) for dx in (-1, 1) for dy in (-1, 1)]
    plate = plate.cut(sockets)
    if magnet_holes:
        magnets = cq.Workplane("XY").pushPoints(corners).circle(magnet_diameter / 2).extrude(2.4)
        plate = plate.cut(magnets)
    return plate
