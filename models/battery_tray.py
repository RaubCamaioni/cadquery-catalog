from typing import Literal
import cadquery as cq

SIZES = {"AAA": (10.5, 44.5), "AA": (14.5, 50.5), "C": (26.2, 50), "18650": (18.6, 65)}


def battery_tray(
    cell: Literal["AAA", "AA", "C", "18650"] = "AA",
    count: int = 8,
    rows: int = 2,
    wall: float = 2,
    depth_fraction: float = 0.6,
) -> cq.Workplane:
    """A tray that holds cells lying down in rows of half-round channels, sized to the cell."""
    diameter, length = SIZES[cell]
    count = max(1, min(count, 40))
    rows = max(1, min(rows, count))
    per_row = -(-count // rows)
    pitch = diameter + wall
    depth_fraction = max(0.3, min(depth_fraction, 0.75))
    width = per_row * pitch + wall
    depth = rows * (length + wall) + wall
    height = diameter * depth_fraction + wall
    tray = cq.Workplane("XY").box(width, depth, height, centered=(True, True, False)).edges("|Z").fillet(2)
    channels = cq.Workplane("XY")
    for r in range(rows):
        y = -depth / 2 + wall + length / 2 + r * (length + wall)
        n = min(per_row, count - r * per_row)
        for c in range(n):
            x = -width / 2 + wall + diameter / 2 + c * pitch
            channel = (
                cq.Workplane("XZ")
                .center(x, height)
                .circle(diameter / 2 + 0.3)
                .extrude(length / 2, both=True)
                .translate((0, y, 0))
            )
            channels = channels.union(channel) if channels.vals() else channel
    return tray.cut(channels)
