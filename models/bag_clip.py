import cadquery as cq


def bag_clip(
    length: float = 80,
    jaw_gap: float = 2,
    arm_thickness: float = 2.4,
    width: float = 12,
    spring_diameter: float = 14,
) -> cq.Workplane:
    """A one-piece spring clip for food bags: two arms joined by a C-shaped spring loop. Prints flat."""
    arm_thickness = max(1.6, arm_thickness)
    r = spring_diameter / 2
    loop = cq.Workplane("XY").circle(r + arm_thickness).circle(r).extrude(width)
    opening = (
        cq.Workplane("XY").center(r, 0).rect(2 * r + 2 * arm_thickness, jaw_gap + 2 * arm_thickness).extrude(width)
    )
    loop = loop.cut(opening)
    arms = (
        cq.Workplane("XY")
        .pushPoints([(length / 2, jaw_gap / 2 + arm_thickness / 2), (length / 2, -jaw_gap / 2 - arm_thickness / 2)])
        .rect(length, arm_thickness)
        .extrude(width)
    )
    # ridges at the jaw tips so the bag is pinched
    tips = (
        cq.Workplane("XY")
        .pushPoints([(length - 3, jaw_gap / 2 - 0.5), (length - 9, -jaw_gap / 2 + 0.5)])
        .rect(2, 1)
        .extrude(width)
    )
    return loop.union(arms).union(tips)
