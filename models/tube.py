import cadquery as cq


def tube(
    outer_diameter: float = 20,
    inner_diameter: float = 16,
    length: float = 50,
    chamfer: float = 0.5,
) -> cq.Workplane:
    """A straight tube or bushing with an optional chamfer on both ends."""
    inner_diameter = max(1, min(inner_diameter, outer_diameter - 1))
    body = cq.Workplane("XY").circle(outer_diameter / 2).circle(inner_diameter / 2).extrude(length)
    chamfer = max(0, min(chamfer, (outer_diameter - inner_diameter) / 4, length / 4))
    if chamfer > 0:
        body = body.faces(">Z or <Z").edges().chamfer(chamfer)
    return body
