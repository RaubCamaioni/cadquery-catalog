# scoop, measuring, kitchen, spoon, volume

import math
import cadquery as cq


def measuring_scoop(
    volume_ml: float = 30,
    handle_length: float = 70,
    wall: float = 1.6,
    handle_width: float = 12,
) -> cq.Workplane:
    """A measuring scoop whose cup holds the requested volume (a hemisphere-bottomed cylinder) with a flat handle."""
    volume_ml = max(2, min(volume_ml, 500))
    wall = max(1, wall)
    # cup: cylinder of radius r and height r on a hemisphere of radius r -> volume = (5/3) pi r^3
    r = (volume_ml * 1000 * 3 / (5 * math.pi)) ** (1 / 3)
    outer_r = r + wall
    cup = (
        cq.Workplane("XZ")
        .moveTo(0, 0)
        .lineTo(outer_r, 0)
        .lineTo(outer_r, -r)
        .threePointArc(
            (outer_r * math.cos(math.radians(45)), -r - outer_r * math.sin(math.radians(45))), (0, -r - outer_r)
        )
        .close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
    )
    inner = (
        cq.Workplane("XZ")
        .moveTo(0, 1)
        .lineTo(r, 1)
        .lineTo(r, -r)
        .threePointArc((r * math.cos(math.radians(45)), -r - r * math.sin(math.radians(45))), (0, -2 * r))
        .close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
    )
    cup = cup.cut(inner)
    handle = (
        cq.Workplane("XY")
        .box(handle_length, handle_width, wall * 2, centered=(False, True, False))
        .translate((outer_r - 2, 0, -wall * 2))
        .edges("|Z")
        .fillet(min(3, handle_width / 3))
    )
    return cup.union(handle)
