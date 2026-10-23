from typing import Literal
import cadquery as cq


def coaster(
    diameter: float = 95,
    thickness: float = 6,
    shape: Literal["round", "hexagon", "square"] = "round",
    recess_depth: float = 2,
    rim: float = 5,
) -> cq.Workplane:
    """A coaster with a shallow recess that catches drips, in a round, hexagonal or square outline."""
    recess_depth = max(0, min(recess_depth, thickness - 1.5))
    rim = max(2, min(rim, diameter / 4))
    if shape == "hexagon":
        outline = cq.Workplane("XY").polygon(6, diameter)
        inner = cq.Workplane("XY").polygon(6, diameter - rim * 2)
    elif shape == "square":
        outline = cq.Workplane("XY").rect(diameter, diameter)
        inner = cq.Workplane("XY").rect(diameter - rim * 2, diameter - rim * 2)
    else:
        outline = cq.Workplane("XY").circle(diameter / 2)
        inner = cq.Workplane("XY").circle(diameter / 2 - rim)
    body = outline.extrude(thickness)
    if shape != "round":
        body = body.edges("|Z").fillet(min(4, rim / 2))
    if recess_depth > 0:
        recess = inner.extrude(recess_depth).translate((0, 0, thickness - recess_depth))
        body = body.cut(recess)
    return body.faces("<Z").chamfer(min(1, thickness / 4))
