import cadquery as cq


def pegboard_bin(
    width: float = 60,
    depth: float = 45,
    height: float = 50,
    wall: float = 1.6,
    hole_spacing: float = 25.4,
    peg_diameter: float = 6,
) -> cq.Workplane:
    """A small bin that hangs on a pegboard by two pegs on its back."""
    wall = max(1, wall)
    bin_ = (
        cq.Workplane("XY")
        .box(width, depth, height, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(4, width / 10))
        .faces(">Z")
        .shell(-wall)
    )
    # two pegs on the back wall, a board hole spacing apart, hooked upward
    pegs = (
        cq.Workplane("XZ")
        .pushPoints([(-hole_spacing / 2, height - 10), (hole_spacing / 2, height - 10)])
        .circle(peg_diameter / 2)
        .extrude(peg_diameter + 4)
        .translate((0, depth / 2, 0))
    )
    lips = (
        cq.Workplane("XZ")
        .pushPoints(
            [
                (-hole_spacing / 2, height - 10 + peg_diameter * 0.75),
                (hole_spacing / 2, height - 10 + peg_diameter * 0.75),
            ]
        )
        .circle(peg_diameter / 2)
        .extrude(4)
        .translate((0, depth / 2 + peg_diameter + 4, 0))
    )
    return bin_.union(pegs).union(lips)
