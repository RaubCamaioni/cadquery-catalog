from typing import Literal
import cadquery as cq


def pen_cup(
    diameter: float = 75,
    height: float = 100,
    wall: float = 1.8,
    shape: Literal["round", "hexagon", "square"] = "round",
    drain_holes: int = 0,
) -> cq.Workplane:
    """A desk cup for pens and tools, round, hexagonal or square, optionally with drain holes."""
    wall = max(0.8, min(wall, diameter / 6))
    drain_holes = max(0, min(drain_holes, 12))
    if shape == "hexagon":
        cup = cq.Workplane("XY").polygon(6, diameter).extrude(height).edges("|Z").fillet(min(4, diameter / 10))
    elif shape == "square":
        cup = cq.Workplane("XY").rect(diameter, diameter).extrude(height).edges("|Z").fillet(min(6, diameter / 8))
    else:
        cup = cq.Workplane("XY").circle(diameter / 2).extrude(height)
    cup = cup.faces(">Z").shell(-wall)
    if drain_holes:
        holes = cq.Workplane("XY").polarArray(max(diameter / 5, 4), 0, 360, drain_holes).circle(2.5).extrude(wall)
        cup = cup.cut(holes)
    return cup.faces("<Z").chamfer(min(0.8, wall / 2))
