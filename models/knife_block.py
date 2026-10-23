import cadquery as cq


def knife_block(
    slots: int = 5,
    slot_length: float = 30,
    slot_width: float = 3.5,
    depth: float = 120,
    width: float = 140,
    height: float = 60,
) -> cq.Workplane:
    """A sloped knife block with a row of blade slots; the top slopes down toward the front so the
    handles present themselves.
    """
    slots = max(1, min(slots, 12))
    block = (
        cq.Workplane("YZ")
        .polyline([(0, 0), (depth, 0), (depth, height * 0.6), (0, height)])
        .close()
        .extrude(width / 2, both=True)
    )
    pitch = (width - 20) / slots
    cuts = (
        cq.Workplane("XY")
        .workplane(offset=8)
        .pushPoints([(-width / 2 + 10 + pitch * (i + 0.5), depth / 2) for i in range(slots)])
        .rect(slot_width, slot_length)
        .extrude(height * 2)
    )
    return block.cut(cuts)
