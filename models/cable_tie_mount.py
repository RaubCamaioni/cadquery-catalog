import cadquery as cq


def cable_tie_mount(
    tie_width: float = 5,
    tie_thickness: float = 1.5,
    base: float = 20,
    height: float = 8,
    screw_hole: float = 3.5,
) -> cq.Workplane:
    """A screw-down anchor for a zip tie: a block with a tunnel the tie threads through."""
    base = max(tie_width + 8, base)
    block = cq.Workplane("XY").box(base, base, height, centered=(True, True, False)).edges("|Z").fillet(2)
    tunnel = (
        cq.Workplane("XZ")
        .center(0, height - tie_thickness / 2 - 1.5)
        .rect(tie_width + 0.6, tie_thickness + 0.6)
        .extrude(base / 2, both=True)
    )
    hole = cq.Workplane("XY").circle(screw_hole / 2).extrude(height)
    head = cq.Workplane("XY").workplane(offset=height - 2.5).circle(screw_hole).extrude(3)
    return block.cut(tunnel).cut(hole).cut(head).faces(">Z").edges().chamfer(0.8)
