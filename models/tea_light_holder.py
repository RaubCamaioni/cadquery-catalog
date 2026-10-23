import cadquery as cq


def tea_light_holder(
    candles: int = 3,
    candle_diameter: float = 39,
    candle_height: float = 16,
    wall: float = 3,
    base_thickness: float = 4,
    spacing: float = 10,
) -> cq.Workplane:
    """A row of cups for tea lights on a shared base; sized for the standard 38 mm cup by default."""
    candles = max(1, min(candles, 8))
    pitch = candle_diameter + 2 * wall + spacing
    length = candles * pitch - spacing
    base = cq.Workplane("XY").slot2D(length, candle_diameter + 2 * wall).extrude(base_thickness)
    points = [(-length / 2 + candle_diameter / 2 + wall + i * pitch, 0) for i in range(candles)]
    cups = (
        cq.Workplane("XY").pushPoints(points).circle(candle_diameter / 2 + wall).extrude(base_thickness + candle_height)
    )
    holes = (
        cq.Workplane("XY")
        .workplane(offset=base_thickness)
        .pushPoints(points)
        .circle(candle_diameter / 2 + 0.5)
        .extrude(candle_height + 1)
    )
    return base.union(cups).cut(holes)
