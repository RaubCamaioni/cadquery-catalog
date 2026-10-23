import cadquery as cq


def yarn_bowl(
    diameter: float = 150,
    height: float = 90,
    wall: float = 2.4,
    slot_width: float = 6,
    holes: int = 3,
) -> cq.Workplane:
    """A yarn bowl: a rounded bowl with a curled slot that the working yarn feeds through, and a
    few holes for extra strands.
    """
    wall = max(1.6, wall)
    r = diameter / 2
    bowl = (
        cq.Workplane("XY")
        .circle(r * 0.7)
        .workplane(offset=height)
        .circle(r)
        .loft()
        .edges(">Z")
        .fillet(min(8, wall * 3))
    )
    cavity = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .circle(r * 0.7 - wall)
        .workplane(offset=height)
        .circle(r - wall)
        .loft()
    )
    bowl = bowl.cut(cavity)
    # the J-slot: a vertical slot from the rim, hooking sideways at the bottom
    slot = cq.Workplane("XZ").center(0, height - height * 0.25).rect(slot_width, height * 0.5 + 1).extrude(-r - 2)
    hook = cq.Workplane("XZ").center(slot_width * 2, height * 0.5).rect(slot_width * 5, slot_width).extrude(-r - 2)
    bowl = bowl.cut(slot).cut(hook)
    if holes:
        pts = (
            cq.Workplane("XZ")
            .center(0, height * 0.55)
            .pushPoints([(-r * 0.5 - i * 15, 0) for i in range(max(1, min(holes, 5)))])
            .circle(4)
            .extrude(-r - 2)
        )
        bowl = bowl.cut(pts)
    return bowl
