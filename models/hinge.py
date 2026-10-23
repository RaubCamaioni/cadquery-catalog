import cadquery as cq


def hinge(
    length: float = 60,
    leaf_width: float = 25,
    thickness: float = 3,
    knuckles: int = 5,
    pin_diameter: float = 4,
    clearance: float = 0.4,
    screw_hole: float = 3.5,
) -> cq.Workplane:
    """A print-in-place hinge: two leaves whose alternating knuckles share one pin, with a
    clearance that prints as a gap. Print it flat; work the joint loose after printing.
    """
    knuckles = max(3, min(knuckles | 1, 15))  # odd: the outer knuckles belong to the same leaf
    seg = length / knuckles
    r = pin_diameter / 2 + thickness
    leaf_a = (
        cq.Workplane("XY")
        .box(leaf_width, length, thickness, centered=(False, True, False))
        .translate((r + clearance, 0, 0))
    )
    leaf_b = (
        cq.Workplane("XY")
        .box(leaf_width, length, thickness, centered=(False, True, False))
        .translate((-r - clearance - leaf_width, 0, 0))
    )
    pin = cq.Workplane("XZ").center(0, r).circle(pin_diameter / 2).extrude(length / 2, both=True)
    for i in range(knuckles):
        y0 = -length / 2 + i * seg
        knuckle = (
            cq.Workplane("XZ")
            .center(0, r)
            .circle(r)
            .circle(pin_diameter / 2 + clearance)
            .extrude(-(seg - clearance))
            .translate((0, y0 + clearance / 2, 0))
        )
        bridge = cq.Workplane("XY").box(r + clearance + 1, seg - clearance, thickness, centered=(False, False, False))
        if i % 2 == 0:
            leaf_a = leaf_a.union(knuckle).union(bridge.translate((0, y0 + clearance / 2, 0)))
        else:
            leaf_b = leaf_b.union(knuckle).union(bridge.translate((-r - clearance - 1, y0 + clearance / 2, 0)))
    holes = (
        cq.Workplane("XY")
        .pushPoints(
            [(r + clearance + leaf_width * 0.6, y) for y in (-length / 3, length / 3)]
            + [(-r - clearance - leaf_width * 0.6, y) for y in (-length / 3, length / 3)]
        )
        .circle(screw_hole / 2)
        .extrude(thickness)
    )
    return leaf_a.union(leaf_b).union(pin).cut(holes)
