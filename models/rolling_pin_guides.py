from pathlib import Path
import cadquery as cq

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _thicknesses(text: str) -> list[float]:
    values = []
    for token in (t.strip() for t in text.replace(";", ",").split(",")):
        if not token:
            continue
        try:
            value = float(token)
        except ValueError:
            raise ValueError(f"thickness {token!r} is not a number of millimetres") from None
        if not 0.5 <= value <= 30:
            raise ValueError(f"thickness {token} mm must be between 0.5 and 30")
        values.append(value)
    if not values:
        raise ValueError("list at least one thickness, like 3, 5, 8")
    return values


def rolling_pin_guides(
    pin_diameter: float = 50,
    thicknesses: str = "3, 5, 8",
    width: float = 12,
    clearance: float = 0.4,
) -> cq.Workplane:
    """Rings that slide onto both ends of a rolling pin so the dough comes out exactly as thick as you
    want: one pair per thickness (comma separated, in mm). The pin rests on the bottom of the bore, so
    each ring is the bore plus twice the thickness across. Measure your pin and set its diameter.

    Printed flat as modelled; the thickness is engraved in the top face."""
    pin_diameter = min(max(pin_diameter, 15), 120)
    clearance = min(max(clearance, 0), 2)
    width = max(width, 4)
    bore = pin_diameter + clearance
    font = {"fontPath": FONT} if Path(FONT).exists() else {}
    rings, x = None, 0.0
    for t in _thicknesses(thicknesses):
        outside = bore + 2 * t
        for _ in range(2):
            x += outside / 2
            ring = cq.Workplane("XY").center(x, 0).circle(outside / 2).circle(bore / 2).extrude(width)
            size = min(0.7 * t, 6)
            if size >= 1.8:
                number = f"{t:g}"
                ring = ring.cut(
                    cq.Workplane("XY")
                    .workplane(offset=width - 0.4)
                    .center(x, -(bore / 2 + t / 2))
                    .text(number, size, 1, halign="center", valign="center", **font)
                )
            rings = ring if rings is None else rings.add(ring)
            x += outside / 2 + 5
    return cq.Workplane().add(cq.Compound.makeCompound([s for s in rings.vals()]))
