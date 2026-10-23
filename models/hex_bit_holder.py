import cadquery as cq


def hex_bit_holder(
    columns: int = 6,
    rows: int = 2,
    bit_size: float = 6.35,
    socket_depth: float = 12,
    spacing: float = 12,
    base_height: float = 18,
) -> cq.Workplane:
    """A block with a grid of hexagonal sockets for screwdriver bits (1/4 inch by default)."""
    columns, rows = max(1, min(columns, 20)), max(1, min(rows, 10))
    across_flats = bit_size + 0.3  # printing clearance
    spacing = max(spacing, across_flats + 2)
    socket_depth = min(socket_depth, base_height - 2)
    width = columns * spacing + 4
    depth = rows * spacing + 4
    block = cq.Workplane("XY").box(width, depth, base_height, centered=(True, True, False)).edges("|Z").fillet(2)
    points = [
        ((c - (columns - 1) / 2) * spacing, (r - (rows - 1) / 2) * spacing) for c in range(columns) for r in range(rows)
    ]
    # polygon() takes the circumscribed diameter; a hex of across-flats f has diameter f / cos(30 deg)
    sockets = (
        cq.Workplane("XY")
        .workplane(offset=base_height)
        .pushPoints(points)
        .polygon(6, across_flats / 0.8660254)
        .extrude(-socket_depth)
    )
    return block.cut(sockets)
