import cadquery as cq


def watch_stand(
    cushion_width: float = 30,
    cushion_depth: float = 45,
    height: float = 60,
    base_diameter: float = 70,
    base_thickness: float = 6,
    cable_slot: float = 5,
) -> cq.Workplane:
    """A watch stand: the strap drapes over a rounded cushion on a post, with a slot through the post
    and base for a charging puck's cable.
    """
    cushion = (
        cq.Workplane("XY")
        .box(cushion_width, cushion_depth, 14, centered=(True, True, False))
        .edges("|X")
        .fillet(6)
        .translate((0, 0, height))
    )
    post = cq.Workplane("XY").center(0, cushion_depth / 2 - 5).rect(cushion_width * 0.6, 8).extrude(height + 1)
    base = cq.Workplane("XY").circle(base_diameter / 2).extrude(base_thickness).faces(">Z").edges().fillet(2)
    stand = base.union(post).union(cushion)
    slot = cq.Workplane("XY").center(0, cushion_depth / 2 - 5).rect(cable_slot, 20).extrude(height + 20)
    return stand.cut(slot)
