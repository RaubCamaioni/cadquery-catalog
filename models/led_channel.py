import cadquery as cq


def led_channel(
    length: float = 200,
    strip_width: float = 10,
    depth: float = 8,
    wall: float = 1.6,
    lip: float = 1.2,
) -> cq.Workplane:
    """A U channel for an LED strip with an inward lip that holds a slide-in diffuser."""
    wall = max(1, wall)
    inner_w = strip_width + 1
    w, h = inner_w + 2 * wall, depth + wall
    channel = cq.Workplane("XY").box(w, length, h, centered=(True, True, False))
    cavity = cq.Workplane("XY").workplane(offset=wall).rect(inner_w, length + 2).extrude(depth)
    channel = channel.cut(cavity)
    # lips: the top of each wall turns inward, leaving a slot for the diffuser below them
    lips = (
        cq.Workplane("XY")
        .workplane(offset=h - lip)
        .pushPoints([(-inner_w / 2 + lip / 2, 0), (inner_w / 2 - lip / 2, 0)])
        .rect(lip, length)
        .extrude(lip)
    )
    return channel.union(lips)
