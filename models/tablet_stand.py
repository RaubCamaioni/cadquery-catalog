import math
import cadquery as cq


def tablet_stand(
    width: float = 120,
    angle: float = 65,
    tablet_thickness: float = 10,
    lip_height: float = 15,
    back_height: float = 110,
    thickness: float = 5,
) -> cq.Workplane:
    """A tablet stand: a base with a front lip and a leaning back plate, with a gap for a cable."""
    angle = max(40, min(angle, 85))
    thickness = max(3, thickness)
    depth = back_height * math.cos(math.radians(angle)) + tablet_thickness + 2 * thickness + 20
    base = cq.Workplane("XY").box(width, depth, thickness, centered=(True, False, False))
    lip = (
        cq.Workplane("XY")
        .box(width, thickness, lip_height + thickness, centered=(True, False, False))
        .translate((0, 10, 0))
    )
    back = (
        cq.Workplane("XY")
        .box(width, thickness, back_height, centered=(True, False, False))
        .rotate((0, 0, 0), (1, 0, 0), -(90 - angle))
        .translate((0, 10 + thickness + tablet_thickness + 2, 0))
    )
    stand = base.union(lip).union(back)
    cable = (
        cq.Workplane("XY")
        .center(0, 10 + thickness + tablet_thickness / 2 + 1)
        .rect(width * 0.25, tablet_thickness + 2)
        .extrude(thickness + 20)
    )
    cable = cable.union(
        cq.Workplane("XY").center(0, 10).rect(width * 0.25, 30).extrude(thickness).translate((0, 0, -0.1))
    )
    return stand.cut(cable)
