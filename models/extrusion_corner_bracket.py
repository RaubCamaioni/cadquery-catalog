import cadquery as cq


def extrusion_corner_bracket(
    profile: float = 20,
    leg_length: float = 20,
    thickness: float = 4,
    slot_hole: float = 5.2,
    gusset: int = 1,
) -> cq.Workplane:
    """An L-shaped corner bracket for square extrusion joints: one hole per leg for an M5 T-nut
    (2020 by default), with an optional triangular gusset.
    """
    thickness = max(3, thickness)
    leg_a = cq.Workplane("XY").box(profile, leg_length, thickness, centered=(True, False, False))
    leg_b = cq.Workplane("XY").box(profile, thickness, leg_length, centered=(True, False, False))
    bracket = leg_a.union(leg_b)
    holes_a = cq.Workplane("XY").center(0, leg_length / 2 + thickness / 2).circle(slot_hole / 2).extrude(thickness)
    holes_b = cq.Workplane("XZ").center(0, leg_length / 2 + thickness / 2).circle(slot_hole / 2).extrude(-thickness)
    bracket = bracket.cut(holes_a).cut(holes_b)
    if gusset:
        web = (
            cq.Workplane("YZ")
            .polyline([(thickness, thickness), (leg_length, thickness), (thickness, leg_length)])
            .close()
            .extrude(thickness / 2, both=True)
        )
        bracket = bracket.union(web.translate((-profile / 2 + thickness / 2, 0, 0))).union(
            web.translate((profile / 2 - thickness / 2, 0, 0))
        )
    return bracket
