import cadquery as cq


def l_bracket(
    leg_a: float = 50,
    leg_b: float = 50,
    width: float = 25,
    thickness: float = 4,
    hole_diameter: float = 4.5,
    holes_per_leg: int = 2,
    gusset: float = 15,
) -> cq.Workplane:
    """An L bracket with countersink-free screw holes on both legs and a triangular gusset."""
    thickness = max(2, thickness)
    holes_per_leg = max(0, min(holes_per_leg, 4))
    gusset = max(0, min(gusset, min(leg_a, leg_b) - thickness))
    base = cq.Workplane("XY").box(leg_a, width, thickness, centered=(False, True, False))
    upright = cq.Workplane("XY").box(thickness, width, leg_b, centered=(False, True, False))
    bracket = base.union(upright)
    if gusset > 0:
        web = (
            cq.Workplane("XZ")
            .polyline([(thickness, thickness), (thickness + gusset, thickness), (thickness, thickness + gusset)])
            .close()
            .extrude(thickness / 2, both=True)
        )
        bracket = bracket.union(web)

    def spots(length):
        start = thickness + gusset + hole_diameter
        if holes_per_leg == 0 or start >= length - hole_diameter:
            return []
        step = (length - hole_diameter - start) / max(1, holes_per_leg - 1) if holes_per_leg > 1 else 0
        return [start + i * step for i in range(holes_per_leg)]

    for x in spots(leg_a):
        bracket = bracket.cut(cq.Workplane("XY").center(x, 0).circle(hole_diameter / 2).extrude(thickness))
    for z in spots(leg_b):
        bracket = bracket.cut(cq.Workplane("YZ").center(0, z).circle(hole_diameter / 2).extrude(thickness))
    return bracket
