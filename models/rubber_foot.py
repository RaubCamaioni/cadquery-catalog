from typing import Literal
import cadquery as cq


def rubber_foot(
    diameter: float = 16,
    height: float = 8,
    taper: float = 2,
    mount: Literal["screw", "adhesive"] = "screw",
    screw_hole: float = 3.5,
    screw_head: float = 7,
) -> cq.Workplane:
    """A tapered foot or bumper for the underside of boxes and furniture, screwed or glued on."""
    taper = max(0, min(taper, diameter / 4))
    foot = cq.Workplane("XY").circle(diameter / 2 - taper).workplane(offset=height).circle(diameter / 2).loft()
    foot = foot.faces("<Z").edges().fillet(min(1, height / 4))
    if mount == "screw":
        hole = cq.Workplane("XY").circle(screw_hole / 2).extrude(height)
        counterbore = cq.Workplane("XY").circle(screw_head / 2).extrude(height / 2)
        foot = foot.cut(hole).cut(counterbore)
    return foot
