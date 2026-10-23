import cadquery as cq


def small_parts_bin(
    width: float = 60,
    depth: float = 90,
    height: float = 40,
    wall: float = 1.6,
    scoop: float = 15,
    label_slot: float = 12,
) -> cq.Workplane:
    """An open parts bin with a scooped front for fingers and a slot for a label card. Bins of the
    same width stack side by side.
    """
    wall = max(0.8, min(wall, width / 8))
    scoop = max(0, min(scoop, height - wall - 3))
    label_slot = max(0, min(label_slot, height - 3))
    bin_ = (
        cq.Workplane("XY")
        .box(width, depth, height, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(3, width / 10))
        .faces(">Z")
        .shell(-wall)
    )
    if scoop > 0:
        cutter = (
            cq.Workplane("XZ")
            .center(0, height)
            .ellipse(width / 2 - wall - 4, scoop)
            .extrude(wall * 2, both=True)
            .translate((0, -depth / 2, 0))
        )
        bin_ = bin_.cut(cutter)
    if label_slot > 0:
        holder = (
            cq.Workplane("XY")
            .box(width - 4, 1.2 + wall, label_slot, centered=(True, False, False))
            .translate((0, -depth / 2 - wall - 1.2, height - label_slot - scoop))
        )
        card = (
            cq.Workplane("XY")
            .box(width - 8, 1.2, label_slot + 1, centered=(True, False, False))
            .translate((0, -depth / 2 - 1.2, height - label_slot - scoop + 1))
        )
        bin_ = bin_.union(holder).cut(card)
    return bin_
