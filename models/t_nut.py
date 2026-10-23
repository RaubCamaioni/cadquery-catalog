import cadquery as cq


def t_nut(
    slot_width: float = 6.2,
    head_width: float = 10,
    head_thickness: float = 3.5,
    neck_height: float = 1.5,
    hole_diameter: float = 4,
    length: float = 10,
) -> cq.Workplane:
    """A drop-in T-nut for aluminium extrusion (2020 slot by default): the head sits in the slot
    behind the lips and a screw taps into the hole. Printed nuts hold light loads only.
    """
    head = cq.Workplane("XY").box(length, head_width, head_thickness, centered=(True, True, False))
    head = head.edges("|X").edges("<Z").chamfer(min(1.2, head_thickness / 3))
    neck = (
        cq.Workplane("XY")
        .box(length, slot_width - 0.3, neck_height + 0.1, centered=(True, True, False))
        .translate((0, 0, head_thickness))
    )
    nut = head.union(neck)
    hole = cq.Workplane("XY").circle(hole_diameter / 2 * 0.9).extrude(head_thickness + neck_height + 1)
    return nut.cut(hole)
