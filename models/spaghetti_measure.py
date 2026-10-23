import math
from pathlib import Path
import cadquery as cq

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DENSITY = 1.45e-3  # g/mm^3, dry durum pasta
PACKING = 0.8  # share of a hand-squeezed bundle that is pasta, not air
MARGIN, GAP, LABEL = 6, 5, 6


def hole_diameter(servings: int, grams_per_serving: float = 85, pasta_length: float = 255) -> float:
    """The hole a bundle of dry spaghetti for that many servings just fills: its weight over density,
    length and packing gives the bundle's area."""
    area = servings * grams_per_serving / (DENSITY * pasta_length * PACKING)
    return 2 * math.sqrt(area / math.pi)


def hole_centres(servings: int = 4, grams_per_serving: float = 85, pasta_length: float = 255) -> list[tuple[float, float]]:
    """Hole centres along the plate, GAP apart edge to edge."""
    centres, x, previous = [], MARGIN, 0.0
    for n in range(1, servings + 1):
        d = hole_diameter(n, grams_per_serving, pasta_length)
        x += (previous / 2 + GAP if previous else 0) + d / 2
        centres.append((x, 0.0))
        previous = d
    return centres


def spaghetti_measure(
    servings: int = 4,
    grams_per_serving: float = 85,
    pasta_length: float = 255,
    thickness: float = 4,
) -> cq.Workplane:
    """A spaghetti portion gauge: one hole per number of servings, each sized so a bundle of dry spaghetti
    that fills it weighs that many servings. Set your serving size in grams and the length of your pasta.
    Printed flat as modelled; the numbers are raised on the top face."""
    servings = min(max(int(servings), 1), 8)
    grams_per_serving = min(max(grams_per_serving, 20), 250)
    pasta_length = min(max(pasta_length, 100), 500)
    thickness = max(thickness, 2.5)
    diameters = [hole_diameter(n, grams_per_serving, pasta_length) for n in range(1, servings + 1)]
    centres = hole_centres(servings, grams_per_serving, pasta_length)
    widest = diameters[-1]
    length = centres[-1][0] + widest / 2 + MARGIN + 10
    low, high = -(widest / 2 + MARGIN), widest / 2 + 2 + LABEL + MARGIN / 2
    plate = (
        cq.Workplane("XY")
        .box(length, high - low, thickness, centered=False)
        .translate((0, low, 0))
        .edges("|Z")
        .fillet(MARGIN)
    )
    for (x, y), d in zip(centres, diameters):
        plate = plate.cut(cq.Workplane().add(cq.Solid.makeCylinder(d / 2, thickness + 2, cq.Vector(x, y, -1))))
    plate = plate.cut(cq.Workplane().add(cq.Solid.makeCylinder(3, thickness + 2, cq.Vector(length - 7, 0, -1))))

    font = {"fontPath": FONT} if Path(FONT).exists() else {}
    for n, ((x, _), d) in enumerate(zip(centres, diameters), start=1):
        number = (
            cq.Workplane("XY")
            .workplane(offset=thickness)
            .center(x, widest / 2 + 2 + LABEL / 2)
            .text(str(n), LABEL, 0.6, halign="center", valign="center", **font)
        )
        plate = plate.union(number)
    return plate
