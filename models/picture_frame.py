import cadquery as cq


def picture_frame(
    photo_width: float = 152,
    photo_height: float = 102,
    border: float = 15,
    depth: float = 10,
    rebate_depth: float = 3,
    stand: float = 60,
) -> cq.Workplane:
    """A photo frame: a border around the opening, a rebate behind it that holds the print and a
    backing, and an optional leaning stand on the back. Sized for a 6x4 inch print by default.
    """
    border = max(5, border)
    depth = max(rebate_depth + 2, depth)
    width, height = photo_width + border * 2, photo_height + border * 2
    frame = (
        cq.Workplane("XY")
        .box(width, height, depth, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(4, border / 3))
    )
    opening = cq.Workplane("XY").rect(photo_width - 6, photo_height - 6).extrude(depth)
    rebate = (
        cq.Workplane("XY")
        .workplane(offset=depth - rebate_depth)
        .rect(photo_width + 1, photo_height + 1)
        .extrude(rebate_depth)
    )
    frame = frame.cut(opening).cut(rebate)
    frame = frame.faces("<Z").edges("not(<X or >X or <Y or >Y)").chamfer(min(2, border / 4))
    if stand > 0:
        leg = (
            cq.Workplane("YZ")
            .polyline([(0, depth), (0, depth + 3), (-stand * 0.9, depth + 3), (-stand, depth)])
            .close()
            .extrude(10, both=True)
            .translate((0, -height / 2 + 2, 0))
        )
        frame = frame.union(leg.rotate((0, -height / 2 + 2, depth), (1, -height / 2 + 2, depth), 0))
    return frame
