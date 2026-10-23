import cadquery as cq


def tolerance_test(
    pin_diameter: float = 6,
    clearances: int = 6,
    step: float = 0.1,
    height: float = 10,
) -> cq.Workplane:
    """A fit test: one pin and a row of holes, each wider than the pin by a growing clearance, so
    the printer's real clearance for press and slip fits can be read off after printing.
    """
    clearances = max(2, min(clearances, 12))
    step = max(0.02, step)
    pitch = pin_diameter + 6
    length = pitch * (clearances + 1) + 10
    plate = (
        cq.Workplane("XY").box(length, pin_diameter + 10, height, centered=(True, True, False)).edges("|Z").fillet(2)
    )
    holes = cq.Workplane("XY")
    for i in range(clearances):
        x = -length / 2 + 5 + pitch * (i + 0.5)
        hole = cq.Workplane("XY").center(x, 0).circle((pin_diameter + step * (i + 1)) / 2).extrude(height)
        holes = holes.union(hole) if holes.vals() else hole
    plate = plate.cut(holes)
    pin = cq.Workplane("XY").center(length / 2 - 5 - pitch / 2, 0).circle(pin_diameter / 2).extrude(height + 8)
    return plate.union(pin)
