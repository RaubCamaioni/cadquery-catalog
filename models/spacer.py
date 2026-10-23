from typing import Literal
import cadquery as cq


def spacer(
    outer_diameter: float = 12,
    hole_diameter: float = 6.4,
    height: float = 10,
    profile: Literal["round", "hex"] = "round",
    chamfer: float = 0.6,
) -> cq.Workplane:
    """A round or hexagonal spacer with a through hole and chamfered ends."""
    if profile == "hex":
        body = cq.Workplane("XY").polygon(6, outer_diameter).extrude(height)
    else:
        body = cq.Workplane("XY").circle(outer_diameter / 2).extrude(height)
    body = body.faces(">Z").workplane().hole(hole_diameter)
    if chamfer > 0:
        body = body.faces(">Z or <Z").edges().chamfer(min(chamfer, height / 3))
    return body
