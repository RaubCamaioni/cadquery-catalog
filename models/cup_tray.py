import cadquery as cq


def cup_tray(
    cup_diameter: float = 30,
    cup_depth: float = 20,
    columns: int = 4,
    rows: int = 3,
    wall: float = 2,
) -> cq.Workplane:
    """A tray with a grid of round cups: paint pots, screws, beads, whatever needs sorting."""
    columns, rows = max(1, min(columns, 12)), max(1, min(rows, 12))
    pitch = cup_diameter + wall
    width, depth = columns * pitch + wall, rows * pitch + wall
    tray = (
        cq.Workplane("XY")
        .box(width, depth, cup_depth + wall, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(4, wall * 2))
    )
    cups = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .pushPoints(
            [
                ((c - (columns - 1) / 2) * pitch, (r - (rows - 1) / 2) * pitch)
                for c in range(columns)
                for r in range(rows)
            ]
        )
        .circle(cup_diameter / 2)
        .extrude(cup_depth + 1)
    )
    return tray.cut(cups)
