import cadquery as cq

GRID = 42.0  # mm per grid unit
UNIT_HEIGHT = 7.0  # mm per height unit


def gridfinity_bin(
    units_x: int = 2,
    units_y: int = 1,
    units_z: int = 3,
    wall: float = 1.2,
    dividers_x: int = 0,
    stacking_lip: int = 1,
) -> cq.Workplane:
    """A Gridfinity-compatible bin: a footprint of 42 mm units with the chamfered base profile that
    sits in a Gridfinity baseplate, a height in 7 mm units, optional dividers and a stacking lip.
    """
    units_x, units_y = max(1, min(units_x, 8)), max(1, min(units_y, 8))
    units_z = max(2, min(units_z, 12))
    dividers_x = max(0, min(dividers_x, units_x * 2))
    w, d = units_x * GRID - 0.5, units_y * GRID - 0.5
    h = units_z * UNIT_HEIGHT
    body = cq.Workplane("XY").box(w, d, h, centered=(True, True, False)).edges("|Z").fillet(3.75)
    # base profile: each unit has a chamfered foot (0.8 + 1.8 + 2.15 mm steps of the spec, simplified to one chamfer)
    feet = None
    for ix in range(units_x):
        for iy in range(units_y):
            cx, cy = (ix - (units_x - 1) / 2) * GRID, (iy - (units_y - 1) / 2) * GRID
            foot = (
                cq.Workplane("XY")
                .center(cx, cy)
                .rect(GRID - 0.5, GRID - 0.5)
                .extrude(4.75)
                .edges("|Z")
                .fillet(3.75)
                .faces("<Z")
                .chamfer(2.6)
            )
            feet = foot if feet is None else feet.union(foot)
    bin_ = body.translate((0, 0, 4.75)).union(feet)
    cavity = (
        cq.Workplane("XY")
        .workplane(offset=4.75 + 1.0)
        .rect(w - 2 * wall, d - 2 * wall)
        .extrude(h)
        .edges("|Z")
        .fillet(max(0.5, 3.75 - wall))
    )
    bin_ = bin_.cut(cavity)
    for i in range(dividers_x):
        x = -w / 2 + (w / (dividers_x + 1)) * (i + 1)
        bin_ = bin_.union(cq.Workplane("XY").center(x, 0).rect(wall, d - 2 * wall + 0.2).extrude(h + 4.75 - 2))
    if stacking_lip:
        lip = (
            cq.Workplane("XY")
            .workplane(offset=h + 4.75)
            .rect(w, d)
            .rect(w - 2 * 1.9, d - 2 * 1.9)
            .extrude(2.4)
            .edges("|Z")
            .fillet(1.0)
        )
        bin_ = bin_.union(lip)
    return bin_
