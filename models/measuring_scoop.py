import math
from fractions import Fraction
from pathlib import Path
from typing import Literal
import cadquery as cq

UNITS_ML = {"ml": 1.0, "tsp": 4.92892, "tbsp": 14.7868, "fl_oz": 29.5735, "cup": 236.5882}
UNIT_TEXT = {"ml": "ml", "tsp": "tsp", "tbsp": "tbsp", "fl_oz": "fl oz", "cup": "cup"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _amount_text(value: float) -> str:
    """1.5 -> '1 1/2', 0.25 -> '1/4', 30 -> '30'."""
    frac = Fraction(value).limit_denominator(8)
    if abs(float(frac) - value) > 1e-3:
        return f"{value:g}"
    whole, rest = divmod(frac, 1)
    return " ".join(p for p in (str(whole) if whole else "", str(rest) if rest else "") if p) or "0"


# the spandrel between a square corner of side f and its quarter-circle fillet: area and centroid offset
SPANDREL_AREA = 1 - math.pi / 4
SPANDREL_CENTROID = (10 - 3 * math.pi) / (3 * (4 - math.pi))


def measuring_scoop(
    volume: float = 30,
    unit: Literal["ml", "tsp", "tbsp", "fl_oz", "cup"] = "ml",
    handle_length: float = 70,
    wall: float = 1.6,
    handle_width: float = 12,
    label: Literal["yes", "no"] = "yes",
) -> cq.Workplane:
    """A measuring scoop that holds exactly the requested volume to the brim, with the amount raised on
    its handle. The bowl is a cylinder as deep as its radius with a rounded inside corner (easy to scrape
    clean); the volume is solved for that exact shape.

    Printed upright as modelled, with no supports: a flat chamfered base and a handle lying on the bed."""
    volume_ml = max(2, min(volume * UNITS_ML[unit], 500))
    wall = max(1, wall)
    # depth = r and fillet f = r / 2: V = pi r^3 - 2 pi (r - c f) A f^2  ->  V = k r^3
    k = math.pi - 2 * math.pi * (1 - SPANDREL_CENTROID / 2) * SPANDREL_AREA / 4
    r = (volume_ml * 1000 / k) ** (1 / 3)
    f, floor = r / 2, max(wall, 1.6)
    rim = floor + r
    outer_r = r + wall
    bowl = cq.Workplane("XY").circle(outer_r).extrude(rim)
    try:
        bowl = bowl.faces("<Z").edges().chamfer(min(0.6, wall / 2))
    except Exception:
        pass
    cavity = (
        cq.Workplane("XZ")
        .moveTo(0, floor)
        .lineTo(r - f, floor)
        .threePointArc((r - f + f * math.cos(math.radians(45)), floor + f - f * math.sin(math.radians(45))), (r, floor + f))
        .lineTo(r, rim + 1)
        .lineTo(0, rim + 1)
        .close()
        .revolve(360, (0, 0, 0), (0, 1, 0))
    )
    thickness = max(3, wall * 2)
    handle = (
        cq.Workplane("XY")
        .box(handle_length + r, handle_width, thickness, centered=(False, True, False))
        .edges("|Z")
        .fillet(min(3, handle_width / 3))
    )
    scoop = bowl.union(handle).cut(cavity)
    if label == "yes":
        text = f"{_amount_text(volume_ml / UNITS_ML[unit])} {UNIT_TEXT[unit]}"
        room = handle_length - 6
        size = min(handle_width * 0.5, room / (0.62 * len(text)))
        font = {"fontPath": FONT} if Path(FONT).exists() else {}
        raised = (
            cq.Workplane("XY")
            .workplane(offset=thickness)
            .center(outer_r + 2 + room / 2, 0)
            .text(text, size, 0.6, halign="center", valign="center", **font)
        )
        scoop = scoop.union(raised)
    return scoop
