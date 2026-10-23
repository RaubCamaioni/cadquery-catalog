from typing import Literal
import cadquery as cq


def knob(
    diameter: float = 30,
    height: float = 18,
    shaft_diameter: float = 6,
    shaft: Literal["round", "d_flat"] = "d_flat",
    grip: Literal["ribbed", "smooth"] = "ribbed",
    ribs: int = 18,
) -> cq.Workplane:
    """A control knob for a round or D-shaped shaft, ribbed or smooth, with a chamfered top."""
    diameter = max(shaft_diameter + 8, diameter)
    ribs = max(6, min(ribs, 60))
    # chamfer the plain cylinder first: the ribs are cut afterwards, past the top, so they stay clean
    body = cq.Workplane("XY").circle(diameter / 2).extrude(height).faces(">Z").chamfer(min(1.5, height / 6))
    if grip == "ribbed":
        rib_r = diameter / ribs
        cutters = cq.Workplane("XY").polarArray(diameter / 2, 0, 360, ribs).circle(rib_r).extrude(height + 2)
        body = body.cut(cutters)
    shaft_hole = cq.Workplane("XY").circle(shaft_diameter / 2 + 0.1).extrude(height - 3)
    if shaft == "d_flat":
        flat = (
            cq.Workplane("XY")
            .center(shaft_diameter / 2 + 0.1, 0)
            .rect(shaft_diameter * 0.45, shaft_diameter * 2)
            .extrude(height - 3)
        )
        shaft_hole = shaft_hole.cut(flat)
    return body.cut(shaft_hole)
