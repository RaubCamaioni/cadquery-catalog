import cadquery as cq


def monitor_riser(
    width: float = 400,
    depth: float = 200,
    height: float = 90,
    top_thickness: float = 8,
    leg_thickness: float = 8,
    cutout: float = 60,
) -> cq.Workplane:
    """A monitor riser: a wide top on two legs, with a cable notch in the back edge. Large; scale it
    to your printer or print the legs separately.
    """
    top_thickness, leg_thickness = max(5, top_thickness), max(5, leg_thickness)
    top = (
        cq.Workplane("XY")
        .box(width, depth, top_thickness, centered=(True, True, False))
        .edges("|Z")
        .fillet(8)
        .translate((0, 0, height - top_thickness))
    )
    legs = (
        cq.Workplane("XY")
        .pushPoints([(-width / 2 + leg_thickness / 2 + 10, 0), (width / 2 - leg_thickness / 2 - 10, 0)])
        .rect(leg_thickness, depth - 20)
        .extrude(height - top_thickness)
    )
    riser = top.union(legs)
    if cutout > 0:
        notch = cq.Workplane("XY").center(0, depth / 2).rect(cutout, 24).extrude(height).edges("|Z").fillet(5)
        riser = riser.cut(notch)
    return riser
