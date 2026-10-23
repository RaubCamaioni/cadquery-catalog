import cadquery as cq


def pencil_tray(
    length: float = 200,
    width: float = 80,
    height: float = 18,
    wall: float = 2,
    grooves: int = 2,
    groove_width: float = 14,
) -> cq.Workplane:
    """A flat desk tray with long rounded grooves that keep pens from rolling, plus a wide pocket."""
    wall = max(1.2, wall)
    grooves = max(0, min(grooves, 6))
    tray = cq.Workplane("XY").box(length, width, height, centered=(True, True, False)).edges("|Z").fillet(6)
    groove_zone = grooves * (groove_width + wall)
    pocket_w = width - groove_zone - 2 * wall
    if pocket_w > 10:
        pocket = (
            cq.Workplane("XY")
            .workplane(offset=wall)
            .center(0, width / 2 - wall - pocket_w / 2)
            .rect(length - 2 * wall, pocket_w)
            .extrude(height)
            .edges("|Z")
            .fillet(4)
        )
        tray = tray.cut(pocket)
    for i in range(grooves):
        y = -width / 2 + wall + groove_width / 2 + i * (groove_width + wall)
        groove = (
            cq.Workplane("YZ")
            .center(y, height)
            .circle(groove_width / 2)
            .extrude(length / 2 - wall, both=True)
            .translate((0, 0, -groove_width / 2 + (height - wall - groove_width / 2) * 0 + 2))
        )
        tray = tray.cut(groove)
    return tray
