import cadquery as cq


def project_box(
    inner_width: float = 80,
    inner_depth: float = 50,
    inner_height: float = 30,
    wall: float = 2,
    lid_thickness: float = 2,
    boss_diameter: float = 6,
    screw_hole: float = 2.5,
) -> cq.Workplane:
    """An electronics enclosure: a box with screw bosses in the corners and a lid that sits on them,
    shown side by side.
    """
    wall = max(1.2, wall)
    w, d, h = inner_width + 2 * wall, inner_depth + 2 * wall, inner_height + wall
    box = (
        cq.Workplane("XY")
        .box(w, d, h, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(3, wall * 1.5))
        .faces(">Z")
        .shell(-wall)
    )
    corners = [
        (ix * (inner_width / 2 - boss_diameter / 2), iy * (inner_depth / 2 - boss_diameter / 2))
        for ix in (-1, 1)
        for iy in (-1, 1)
    ]
    bosses = (
        cq.Workplane("XY").workplane(offset=wall).pushPoints(corners).circle(boss_diameter / 2).extrude(inner_height)
    )
    holes = (
        cq.Workplane("XY").workplane(offset=wall + 3).pushPoints(corners).circle(screw_hole / 2).extrude(inner_height)
    )
    box = box.union(bosses).cut(holes)
    lid = (
        cq.Workplane("XY")
        .box(w, d, lid_thickness, centered=(True, True, False))
        .edges("|Z")
        .fillet(min(3, wall * 1.5))
        .cut(cq.Workplane("XY").pushPoints(corners).circle(screw_hole / 2 + 0.6).extrude(lid_thickness))
        .translate((w + 10, 0, 0))
    )
    return box.union(lid)
