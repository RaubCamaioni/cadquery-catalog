import cadquery as cq


def thread_spool_rack(
    columns: int = 6,
    rows: int = 4,
    peg_diameter: float = 6,
    peg_height: float = 35,
    pitch: float = 30,
    base_thickness: float = 5,
    tilt: float = 10,
) -> cq.Workplane:
    """A sewing thread rack: a plate of pegs, each tilted back so spools stay on when the rack hangs
    on a wall, with keyhole screw slots.
    """
    columns, rows = max(1, min(columns, 12)), max(1, min(rows, 12))
    width, height = columns * pitch + 10, rows * pitch + 10
    plate = cq.Workplane("XY").box(width, height, base_thickness, centered=(True, True, False)).edges("|Z").fillet(5)
    pts = [
        (-width / 2 + 5 + pitch * (c + 0.5), -height / 2 + 5 + pitch * (r + 0.5))
        for c in range(columns)
        for r in range(rows)
    ]
    for p in pts:
        peg = (
            cq.Workplane("XY")
            .circle(peg_diameter / 2)
            .extrude(peg_height)
            .faces(">Z")
            .chamfer(peg_diameter / 4)
            .rotate((0, 0, 0), (1, 0, 0), -tilt)
            .translate((p[0], p[1], base_thickness - 0.5))
        )
        plate = plate.union(peg)
    slots = (
        cq.Workplane("XY")
        .pushPoints([(-width / 3, height / 2 - 8), (width / 3, height / 2 - 8)])
        .slot2D(10, 4.5, angle=90)
        .extrude(base_thickness)
    )
    return plate.cut(slots)
