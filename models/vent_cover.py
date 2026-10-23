import cadquery as cq


def vent_cover(
    width: float = 150,
    height: float = 100,
    frame: float = 10,
    thickness: float = 3,
    louvers: int = 6,
    louver_angle: float = 35,
    screw_hole: float = 4,
) -> cq.Workplane:
    """A louvered vent cover: a frame with angled slats that let air through but hide the duct."""
    louvers = max(1, min(louvers, 20))
    frame = max(5, frame)
    plate = cq.Workplane("XY").box(width, height, thickness, centered=(True, True, False)).edges("|Z").fillet(4)
    opening = cq.Workplane("XY").rect(width - 2 * frame, height - 2 * frame).extrude(thickness)
    cover = plate.cut(opening)
    inner_h = height - 2 * frame
    pitch = inner_h / louvers
    slat_w = pitch * 1.3
    for i in range(louvers):
        y = -inner_h / 2 + pitch * (i + 0.5)
        slat = (
            cq.Workplane("XY")
            .box(width - 2 * frame + 2, slat_w, thickness * 0.6, centered=(True, True, True))
            .rotate((0, 0, 0), (1, 0, 0), louver_angle)
            .translate((0, y, thickness / 2))
        )
        cover = cover.union(slat)
    cover = cover.intersect(
        cq.Workplane("XY").box(width, height, thickness * 3, centered=(True, True, False)).translate((0, 0, -thickness))
    )
    holes = (
        cq.Workplane("XY")
        .pushPoints(
            [
                (x, y)
                for x in (-width / 2 + frame / 2, width / 2 - frame / 2)
                for y in (-height / 2 + frame / 2, height / 2 - frame / 2)
            ]
        )
        .circle(screw_hole / 2)
        .extrude(thickness * 3)
        .translate((0, 0, -thickness))
    )
    return cover.cut(holes)
