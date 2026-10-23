import cadquery as cq


def cable_spool(
    length: float = 80,
    width: float = 36,
    thickness: float = 6,
    notch_width: float = 10,
    notch_depth: float = 14,
    slot_width: float = 4,
) -> cq.Workplane:
    """A bone-shaped cord winder: the cable wraps around the waist and its ends tuck into the notches."""
    thickness = max(3, thickness)
    body = cq.Workplane("XY").slot2D(length, width).extrude(thickness)
    notches = (
        cq.Workplane("XY")
        .pushPoints([(-length / 2 + notch_depth / 2, 0), (length / 2 - notch_depth / 2, 0)])
        .rect(notch_depth, notch_width)
        .extrude(thickness)
    )
    waist = cq.Workplane("XY").pushPoints([(0, width / 2), (0, -width / 2)]).circle(width / 4).extrude(thickness)
    slot = cq.Workplane("XY").slot2D(length / 2, slot_width).extrude(thickness)
    return body.cut(notches).cut(waist).cut(slot).edges("|Z").fillet(min(1.5, slot_width / 3))
