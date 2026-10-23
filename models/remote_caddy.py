import cadquery as cq


def remote_caddy(
    slots: int = 3,
    slot_width: float = 50,
    slot_depth: float = 22,
    height: float = 70,
    wall: float = 2,
    front_dip: float = 25,
) -> cq.Workplane:
    """A caddy with side-by-side slots for remote controls; the front of each slot dips so the
    remotes are easy to grab.
    """
    slots = max(1, min(slots, 8))
    wall = max(1.2, wall)
    length = slots * (slot_width + wall) + wall
    depth = slot_depth + 2 * wall
    body = cq.Workplane("XY").box(length, depth, height, centered=(True, True, False)).edges("|Z").fillet(3)
    for i in range(slots):
        x = -length / 2 + wall + slot_width / 2 + i * (slot_width + wall)
        pocket = cq.Workplane("XY").workplane(offset=wall).center(x, 0).rect(slot_width, slot_depth).extrude(height)
        dip = (
            cq.Workplane("XY")
            .workplane(offset=height - front_dip)
            .center(x, -depth / 2)
            .rect(slot_width * 0.6, 2 * wall + 1)
            .extrude(front_dip + 1)
        )
        body = body.cut(pocket).cut(dip)
    return body
