import cadquery as cq


def ruler(
    length_mm: int = 150,
    width: float = 25,
    thickness: float = 2,
    tick_depth: float = 0.6,
    hang_hole: float = 5,
) -> cq.Workplane:
    """A ruler with engraved millimetre ticks: short every mm, medium every 5 mm, long every 10 mm."""
    length_mm = max(20, min(int(length_mm), 400))
    thickness = max(1.2, thickness)
    tick_depth = max(0.2, min(tick_depth, thickness - 0.6))
    body = (
        cq.Workplane("XY").box(length_mm + 10, width, thickness, centered=(False, False, False)).edges("|Z").fillet(2)
    )
    groups = {3: [], 5: [], 8: []}
    for mm in range(0, length_mm + 1):
        h = 8 if mm % 10 == 0 else 5 if mm % 5 == 0 else 3
        groups[h].append((5 + mm, h / 2))
    for h, pts in groups.items():
        if pts:
            ticks = (
                cq.Workplane("XY")
                .workplane(offset=thickness - tick_depth)
                .pushPoints(pts)
                .rect(0.4, h)
                .extrude(tick_depth + 1)
            )
            body = body.cut(ticks)
    if hang_hole > 0:
        body = body.cut(cq.Workplane("XY").center(length_mm + 5, width - 6).circle(hang_hole / 2).extrude(thickness))
    return body
