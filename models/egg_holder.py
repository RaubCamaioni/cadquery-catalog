import cadquery as cq


def egg_holder(
    columns: int = 6,
    rows: int = 2,
    egg_diameter: float = 45,
    pitch: float = 50,
    thickness: float = 12,
    wall: float = 2,
) -> cq.Workplane:
    """A tray with dished pockets that hold eggs upright, for a fridge shelf or counter."""
    columns, rows = max(1, min(columns, 12)), max(1, min(rows, 6))
    pitch = max(egg_diameter + wall, pitch)
    width, depth = columns * pitch, rows * pitch
    tray = cq.Workplane("XY").box(width, depth, thickness, centered=(True, True, False)).edges("|Z").fillet(6)
    pts = [
        (-width / 2 + pitch * (c + 0.5), -depth / 2 + pitch * (r + 0.5)) for c in range(columns) for r in range(rows)
    ]
    dishes = (
        cq.Workplane("XY")
        .workplane(offset=thickness + egg_diameter * 0.35)
        .pushPoints(pts)
        .sphere(egg_diameter / 2, combine=False)
    )
    return tray.cut(dishes)
