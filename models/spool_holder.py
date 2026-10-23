import cadquery as cq


def spool_holder(
    spool_width: float = 70,
    spool_hole: float = 52,
    axle_diameter: float = 30,
    height: float = 90,
    base_depth: float = 90,
    thickness: float = 8,
) -> cq.Workplane:
    """A tabletop spool holder: two uprights on a base with an axle the spool hangs on, shown as one
    print (the axle is a separate part laid beside the stand).
    """
    axle_diameter = max(10, min(axle_diameter, spool_hole - 4))
    width = spool_width + 2 * thickness + 10
    base = cq.Workplane("XY").box(width, base_depth, thickness, centered=(True, True, False)).edges("|Z").fillet(5)
    uprights = (
        cq.Workplane("XY")
        .pushPoints([(-width / 2 + thickness / 2, 0), (width / 2 - thickness / 2, 0)])
        .rect(thickness, base_depth * 0.5)
        .extrude(height)
    )
    notch = (
        cq.Workplane("YZ")
        .center(0, height)
        .rect(axle_diameter + 1, axle_diameter * 1.5)
        .extrude(width / 2 + 1, both=True)
        .translate((0, 0, -axle_diameter * 0.25))
    )
    seat = (
        cq.Workplane("YZ")
        .center(0, height - axle_diameter / 2 - 0.5)
        .circle(axle_diameter / 2 + 0.5)
        .extrude(width / 2 + 1, both=True)
    )
    stand = base.union(uprights).cut(notch).cut(seat)
    axle = (
        cq.Workplane("YZ")
        .circle(axle_diameter / 2)
        .extrude(width / 2 + 10, both=True)
        .translate((0, base_depth / 2 + axle_diameter, axle_diameter / 2))
    )
    return stand.union(axle)
