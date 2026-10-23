import cadquery as cq


def bearing_holder(
    bearing_od: float = 22,
    bearing_width: float = 7,
    bore: float = 8,
    flange: float = 6,
    clearance: float = 0.15,
    screw_holes: int = 4,
    screw_hole: float = 3.4,
) -> cq.Workplane:
    """A flanged pocket that holds a ball bearing (608 by default) with screw holes around it."""
    screw_holes = max(0, min(screw_holes, 8))
    outer = bearing_od + 2 * clearance + 2 * 3
    body = (
        cq.Workplane("XY")
        .circle(outer / 2 + flange)
        .extrude(3)
        .faces(">Z")
        .workplane()
        .circle(outer / 2)
        .extrude(bearing_width)
    )
    pocket = cq.Workplane("XY").workplane(offset=3).circle(bearing_od / 2 + clearance).extrude(bearing_width)
    through = cq.Workplane("XY").circle(max(bore, bearing_od - 6) / 2).extrude(3)
    holder = body.cut(pocket).cut(through)
    if screw_holes:
        holes = (
            cq.Workplane("XY").polarArray(outer / 2 + flange / 2, 0, 360, screw_holes).circle(screw_hole / 2).extrude(3)
        )
        holder = holder.cut(holes)
    return holder
