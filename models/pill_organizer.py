import cadquery as cq


def pill_organizer(
    compartments: int = 7,
    compartment_width: float = 25,
    compartment_depth: float = 30,
    height: float = 20,
    wall: float = 1.6,
    rows: int = 1,
) -> cq.Workplane:
    """A tray of equal compartments (seven for a week, two rows for morning and evening) with
    rounded pockets that are easy to pick from.
    """
    compartments, rows = max(1, min(compartments, 14)), max(1, min(rows, 4))
    wall = max(1.2, wall)
    width = compartments * (compartment_width + wall) + wall
    depth = rows * (compartment_depth + wall) + wall
    tray = cq.Workplane("XY").box(width, depth, height, centered=(True, True, False)).edges("|Z").fillet(3)
    pts = [
        (
            -width / 2 + wall + compartment_width / 2 + c * (compartment_width + wall),
            -depth / 2 + wall + compartment_depth / 2 + r * (compartment_depth + wall),
        )
        for c in range(compartments)
        for r in range(rows)
    ]
    pockets = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .pushPoints(pts)
        .rect(compartment_width, compartment_depth)
        .extrude(height)
        .edges("|Z")
        .fillet(min(4, compartment_width / 4))
    )
    return tray.cut(pockets)
