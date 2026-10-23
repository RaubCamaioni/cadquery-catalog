# scoop, measuring, kitchen, spoon, volume, ml, oz, label

import math
from typing import Literal
import cadquery as cq

ML_PER_OZ = 29.5735

# stroke font for the label (the sandbox has no system fonts): polylines on a grid 6 units tall, advance = width
GLYPHS = {
    "0": (4, [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)]]),
    "1": (4, [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]]),
    "2": (4, [[(0, 6), (4, 6), (4, 3), (0, 3), (0, 0), (4, 0)]]),
    "3": (4, [[(0, 6), (4, 6), (4, 0), (0, 0)], [(1, 3), (4, 3)]]),
    "4": (4, [[(0, 6), (0, 3), (4, 3)], [(4, 6), (4, 0)]]),
    "5": (4, [[(4, 6), (0, 6), (0, 3), (4, 3), (4, 0), (0, 0)]]),
    "6": (4, [[(4, 6), (0, 6), (0, 0), (4, 0), (4, 3), (0, 3)]]),
    "7": (4, [[(0, 6), (4, 6), (4, 0)]]),
    "8": (4, [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)], [(0, 3), (4, 3)]]),
    "9": (4, [[(4, 3), (0, 3), (0, 6), (4, 6), (4, 0), (0, 0)]]),
    ".": (0, [[(0, 0)]]),
    "m": (4, [[(0, 0), (0, 4), (4, 4), (4, 0)], [(2, 4), (2, 0)]]),
    "l": (0, [[(0, 6), (0, 0)]]),
    "o": (3, [[(0, 0), (3, 0), (3, 4), (0, 4), (0, 0)]]),
    "z": (3, [[(0, 4), (3, 4), (0, 0), (3, 0)]]),
    " ": (1, []),
}
GAP = 2  # grid units between glyphs


def _label_width(text: str) -> float:
    return sum(GLYPHS[c][0] for c in text) + GAP * (len(text) - 1)


def _label(text: str, unit: float, stroke: float, height: float) -> cq.Workplane:
    """Raised stroke text with its baseline on y=0, starting at x=0, standing on z=0."""
    solid = None
    x = 0.0
    for c in text:
        width, lines = GLYPHS[c]
        for line in lines:
            points = [((x + px) * unit, py * unit) for px, py in line]
            if len(points) == 1:
                pieces = [cq.Workplane("XY").center(*points[0]).circle(stroke / 2).extrude(height)]
            else:
                pieces = []
                for (x0, y0), (x1, y1) in zip(points, points[1:]):
                    length = math.hypot(x1 - x0, y1 - y0)
                    angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
                    pieces.append(
                        cq.Workplane("XY")
                        .center((x0 + x1) / 2, (y0 + y1) / 2)
                        .slot2D(length + stroke, stroke, angle)
                        .extrude(height)
                    )
            for piece in pieces:
                solid = piece if solid is None else solid.union(piece)
        x += width + GAP
    return solid


def measuring_scoop(
    volume: float = 30,
    unit: Literal["ml", "oz"] = "ml",
    handle_length: float = 70,
    wall: float = 1.6,
    handle_width: float = 12,
) -> cq.Workplane:
    """A measuring scoop whose cup holds the requested volume (a hemisphere-bottomed cylinder) with a flat handle.

    The volume is in millilitres or US fluid ounces; the handle carries the volume and unit as raised text.
    """
    ml_per_unit = ML_PER_OZ if unit == "oz" else 1
    volume_ml = max(2, min(volume * ml_per_unit, 500))
    wall = max(1, wall)
    handle_width = max(8, handle_width)
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
    scoop = cup.union(handle)

    # the label shows the volume as entered (after clamping), with at most one decimal
    shown = round(volume_ml / ml_per_unit, 1)
    text = f"{shown:g} {unit}"
    # the label sits on the handle top between the cup rim and the rounded end, sized to fit both ways
    start, end = outer_r + 2, outer_r - 2 + handle_length - 4
    unit_mm = min(handle_width * 0.6 / 6, (end - start) / _label_width(text), 1.5)
    if unit_mm < 0.5:
        return scoop  # too small to print legibly
    stroke = max(0.8, unit_mm * 0.9)
    text_solid = _label(text, unit_mm, stroke, 0.6)
    offset_x = start + (end - start - _label_width(text) * unit_mm) / 2
    return scoop.union(text_solid.translate((offset_x, -3 * unit_mm, 0)))
