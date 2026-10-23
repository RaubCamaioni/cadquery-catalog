import cadquery as cq


def twisted_vase(
    sides: int = 6,
    diameter: float = 70,
    height: float = 150,
    twist_degrees: float = 90,
    wall: float = 1.6,
    floor: float = 2,
) -> cq.Workplane:
    """A polygonal vase that twists as it rises, hollow with a solid floor. Prints well in vase mode."""
    sides = max(3, min(int(sides), 16))
    twist_degrees = max(-360, min(twist_degrees, 360))
    wall = max(0.8, min(wall, diameter / 8))
    outer = cq.Workplane("XY").polygon(sides, diameter).twistExtrude(height, twist_degrees)
    inner = (
        cq.Workplane("XY")
        .workplane(offset=floor)
        .polygon(sides, diameter - 2 * wall)
        .twistExtrude(height, twist_degrees * (height) / height)
    )
    return outer.cut(inner)
