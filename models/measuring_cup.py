import math
from fractions import Fraction
from pathlib import Path
from typing import Literal
import cadquery as cq

UNITS_ML = {"cup": 236.5882, "metric_cup": 250.0, "ml": 1.0, "fl_oz": 29.5735, "tbsp": 14.7868, "tsp": 4.92892}
UNIT_TEXT = {"cup": "cup", "metric_cup": "cup", "ml": "ml", "fl_oz": "fl oz", "tbsp": "tbsp", "tsp": "tsp"}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
GROOVE_DEPTH, RAISE, HANDLE_THICKNESS = 0.6, 0.6, 12


def _amount(text: str) -> Fraction:
    """'1/4', '1 1/2', '0.5' or '250' as a positive number."""
    try:
        value = sum((Fraction(part) for part in text.split()), Fraction(0))
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"marker {text!r} is not a number like 1/4, 1 1/2 or 250") from None
    if value <= 0:
        raise ValueError(f"marker {text!r} must be more than zero")
    return value


def _amount_text(value: float) -> str:
    """1.5 -> '1 1/2', 0.333 -> '1/3', 250 -> '250'."""
    frac = Fraction(value).limit_denominator(8)
    if abs(float(frac) - value) > 1e-3:
        return f"{value:g}"
    whole, rest = divmod(frac, 1)
    return " ".join(p for p in (str(whole) if whole else "", str(rest) if rest else "") if p) or "0"


def _cup(capacity, unit, inner_diameter, headroom, wall, taper):
    """Floor thickness, bottom inside radius, tan(taper), capacity in mm^3, wall and headroom."""
    volume = min(max(capacity * UNITS_ML[unit], 5), 2000) * 1000
    tan = math.tan(math.radians(min(max(taper, 0), 10)))
    r0 = inner_diameter / 2 if inner_diameter > 0 else 0.95 * (volume / (1.6 * math.pi)) ** (1 / 3)
    wall = max(wall, 1.2)
    return max(wall, 1.6), r0, tan, volume, wall, max(headroom, 0)


def _frustum(h, r0, tan):
    r = r0 + h * tan
    return math.pi * h / 3 * (r0 * r0 + r0 * r + r * r)


def _groove(r):
    """Volume a line's groove adds: a right triangle, GROOVE_DEPTH on each side, revolved at radius r."""
    return math.pi * (r + GROOVE_DEPTH / 3) * GROOVE_DEPTH**2


def _height(volume, r0, tan):
    lo, hi = 0.0, 1.0
    while _frustum(hi, r0, tan) < volume:
        hi *= 2
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _frustum(mid, r0, tan) < volume else (lo, mid)
    return (lo + hi) / 2


def marker_levels(
    capacity: float = 1,
    unit: str = "cup",
    markers: str = "1/4, 1/3, 1/2, 2/3, 3/4",
    marker_unit: str = "same",
    inner_diameter: float = 0,
    headroom: float = 10,
    wall: float = 2,
    taper: float = 3,
    **_,
) -> list[tuple[str, float, float, bool]]:
    """(label, ml, height of the line, grooved) for every line, lowest first. Each height is solved so the
    cup holds exactly that much below it, the grooves of the lines below included (a line's own groove
    sits above it)."""
    floor, r0, tan, volume, wall, headroom = _cup(capacity, unit, inner_diameter, headroom, wall, taper)
    own = unit if marker_unit == "same" else marker_unit
    wanted = {}
    for token in (t.strip() for t in markers.replace(";", ",").split(",")):
        if token:
            ml = float(_amount(token)) * UNITS_ML[own]
            if ml * 1000 > volume * 1.0001:
                raise ValueError(f"marker {token} {UNIT_TEXT[own]} is more than the cup holds")
            wanted.setdefault(round(ml, 6), " ".join(token.split()))
    if wanted and own != unit:
        top = max(wanted)
        wanted[top] = f"{wanted[top]} {UNIT_TEXT[own]}"
    capacity_ml = round(volume / 1000, 6)
    wanted = {ml: text for ml, text in wanted.items() if abs(ml - capacity_ml) > 1e-3}
    wanted[capacity_ml] = f"{_amount_text(volume / 1000 / UNITS_ML[unit])} {UNIT_TEXT[unit]}"
    levels, below = [], 0.0
    for ml in sorted(wanted):
        grooved = headroom > 0 or ml < capacity_ml
        h = _height(ml * 1000 - below, r0, tan)
        if grooved:
            below += _groove(r0 + h * tan)
        levels.append((wanted[ml], ml, floor + h, grooved))
    return levels


def inner_radius_at(z: float, capacity=1, unit="cup", inner_diameter=0, headroom=10, wall=2, taper=3, **_) -> float:
    floor, r0, tan, *_rest = _cup(capacity, unit, inner_diameter, headroom, wall, taper)
    return r0 + (z - floor) * tan


def _revolve(points):
    return cq.Workplane("XZ").polyline(points).close().revolve(360, (0, 0, 0), (0, 1, 0))


def _text(plane: cq.Workplane, text: str, size: float, depth: float, halign: str = "center") -> cq.Workplane:
    font = {"fontPath": FONT} if Path(FONT).exists() else {}
    return plane.text(text, size, depth, halign=halign, valign="center", **font)


def measuring_cup(
    capacity: float = 1,
    unit: Literal["cup", "metric_cup", "ml", "fl_oz", "tbsp", "tsp"] = "cup",
    markers: str = "1/4, 1/3, 1/2, 2/3, 3/4",
    marker_unit: Literal["same", "cup", "metric_cup", "ml", "fl_oz", "tbsp", "tsp"] = "same",
    inner_diameter: float = 0,
    headroom: float = 10,
    wall: float = 2,
    taper: float = 3,
    handle_length: float = 32,
    spout: Literal["yes", "no"] = "yes",
) -> cq.Workplane:
    """A measuring cup with a line inside at every amount you list (comma separated: 1/4, 1 1/2, 250),
    each at the exact height for that volume, labelled on the outside. Markers use the cup's unit unless
    marker_unit says otherwise. headroom is the wall above the capacity line; 0 makes a dry cup that
    measures to the brim. inner_diameter 0 picks a cup about as tall as it is wide.

    Printed upright as modelled, with no supports: a flat chamfered base, a jug handle standing on the
    bed with a 45 degree peak over the finger hole, grooves with a flat lower edge (the line) and a 45
    degree roof, and labels raised on the side wall."""
    floor, r0, tan, volume, wall, headroom = _cup(capacity, unit, inner_diameter, headroom, wall, taper)
    levels = marker_levels(capacity, unit, markers, marker_unit, inner_diameter, headroom, wall, taper)
    top = levels[-1][2] + headroom if headroom > 0 else levels[-1][2]  # a dry cup's brim is the capacity line

    def r_in(z):
        return r0 + (z - floor) * tan

    def r_out(z):
        return r_in(z) + wall

    outer = _revolve([(0, 0), (r_out(0), 0), (r_out(top), top), (0, top)])
    try:
        outer = outer.faces("<Z").edges().chamfer(min(0.8, wall / 2))  # a 45 degree foot, no first-layer bulge
    except Exception:
        pass

    # a jug handle standing on the bed: a solid grip on a short cup, a loop with a 45 degree peak otherwise
    reach = max(handle_length, 28)
    x0, xr, corner = r_out(0) - wall / 2, r_out(top) + reach, 8
    grip = (
        cq.Workplane("XZ")
        .polyline([(xr - corner, top), (x0, top), (x0, 0), (xr, 0), (xr, top - corner)])
        .threePointArc((xr - corner + corner * math.cos(math.radians(45)), top - corner + corner * math.sin(math.radians(45))), (xr - corner, top))
        .close()
        .extrude(HANDLE_THICKNESS / 2, both=True)
    )
    xi0, xi1 = r_out(top) + 3, xr - 9
    apex = top - 8
    eave = apex - (xi1 - xi0) / 2
    if xi1 - xi0 >= 15 and eave >= 18:
        finger = cq.Workplane("XZ").polyline([(xi0, 8), (xi1, 8), (xi1, eave), ((xi0 + xi1) / 2, apex), (xi0, eave)]).close()
        grip = grip.cut(finger.extrude(HANDLE_THICKNESS, both=True))
    cup = outer.union(grip).cut(_revolve([(0, floor), (r_in(floor), floor), (r_in(top + 1), top + 1), (0, top + 1)]))

    for _label, _ml, z, grooved in levels:
        if grooved:
            r, d = r_in(z), GROOVE_DEPTH
            cup = cup.cut(_revolve([(r - 0.3, z), (r + d, z), (r - 0.3, z + d + 0.3)]))

    # ticks and labels raised on the outside wall, facing -Y; alternate sides of the tick so close lines
    # stay readable. A dry cup's brim carries the capacity label without a tick.
    labelled = [(text, z, grooved) for text, _ml, z, grooved in levels]
    heights = [z for _t, z, g in labelled if g]
    gaps = [b - a for a, b in zip(heights, heights[1:])] or [10]
    longest = max(len(text) for text, _z, _g in labelled)
    size = min(7, max(2.5, 1.6 * min(gaps)), max(2.5, (0.8 * r_out(floor) - 4) / (0.62 * longest)))
    marks = []
    for i, (text, z, grooved) in enumerate(labelled):
        if grooved:
            marks.append(cq.Workplane("XZ").center(0, z + 0.4).rect(6, 0.8).extrude(r_out(top) + 3).val())
        z = min(max(z, size / 2 + 0.5), top - size / 2 - 1)
        side = 1 if i % 2 == 0 or not grooved else -1
        x = side * 4 if grooved else 0
        label = _text(cq.Workplane("XZ").center(x, z), text, size, r_out(top) + 3, "center" if not grooved else "left" if side > 0 else "right")
        marks += label.vals()
    inset = min(0.6, wall / 2)
    shell = _revolve([(r_out(0) - inset, 1), (r_out(0) + RAISE, 1), (r_out(top) + RAISE, top), (r_out(top) - inset, top)])
    cup = cup.union(shell.intersect(cq.Workplane().add(cq.Compound.makeCompound(marks))))

    if spout == "yes" and headroom >= 3:
        rho, depth = max(6, r_out(top) * 0.3), min(headroom * 0.6, 6)
        start = r_out(top) + 5
        notch = cq.Solid.makeCylinder(rho, start - r_in(top) * 0.6, cq.Vector(-start, 0, top + rho - depth), cq.Vector(1, 0, 0))
        cup = cup.cut(cq.Workplane().add(notch))
    return cup
