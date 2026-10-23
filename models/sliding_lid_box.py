import cadquery as cq


def sliding_lid_box(
    length: float = 100,
    width: float = 60,
    height: float = 40,
    wall: float = 2.4,
    lid_thickness: float = 2,
    clearance: float = 0.3,
) -> cq.Workplane:
    """A box with a lid that slides in grooves along the long sides; the lid is placed next to the
    box so both print together.
    """
    wall = max(1.6, wall)
    groove = lid_thickness + clearance
    body = cq.Workplane("XY").box(length, width, height, centered=(True, True, False))
    cavity = cq.Workplane("XY").workplane(offset=wall).rect(length - 2 * wall, width - 2 * wall).extrude(height)
    body = body.cut(cavity)
    # the groove: a slot through both long walls and one end wall, just under the top
    slot = (
        cq.Workplane("XY")
        .workplane(offset=height - wall - groove)
        .center(wall / 2 + 0.5, 0)
        .rect(length - wall + 1, width - wall)
        .extrude(groove)
    )
    body = body.cut(slot)
    # the lid, with a thumb ridge at one end, lying beside the box
    lid_len = length - wall / 2 - 0.5
    lid_w = width - wall - 2 * clearance
    lid = cq.Workplane("XY").box(lid_len, lid_w, lid_thickness, centered=(True, True, False))
    ridge = (
        cq.Workplane("XY")
        .box(6, lid_w, lid_thickness + 1.5, centered=(True, True, False))
        .translate((lid_len / 2 - 3, 0, 0))
    )
    lid = lid.union(ridge).translate((0, width + 10, 0))
    return body.union(lid)
