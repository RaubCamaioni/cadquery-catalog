import cadquery as cq


def glasses_stand(
    width: float = 150,
    bridge_depth: float = 40,
    height: float = 70,
    thickness: float = 4,
    nose_width: float = 20,
) -> cq.Workplane:
    """A bedside stand for a pair of glasses: a T-shaped nose rest on a base; the temples hang
    down either side.
    """
    thickness = max(3, thickness)
    base = (
        cq.Workplane("XY")
        .box(width * 0.5, bridge_depth + 20, thickness, centered=(True, True, False))
        .edges("|Z")
        .fillet(5)
    )
    post = cq.Workplane("XY").rect(nose_width, thickness).extrude(height)
    rest = (
        cq.Workplane("XY")
        .box(nose_width + 10, bridge_depth, thickness, centered=(True, True, False))
        .translate((0, 0, height))
        .edges("|Z")
        .fillet(3)
    )
    # a shallow groove across the rest keeps the bridge in place
    groove = cq.Workplane("YZ").center(0, height + thickness).circle(3).extrude(nose_width + 12, both=True)
    return base.union(post).union(rest).cut(groove)
