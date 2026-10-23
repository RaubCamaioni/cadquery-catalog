import cadquery as cq


def bookend(
    height: float = 150,
    depth: float = 120,
    width: float = 100,
    thickness: float = 4,
    weight_pocket: float = 40,
    lip: float = 8,
) -> cq.Workplane:
    """An L-shaped bookend whose foot slides under the books; the foot has a pocket for ballast
    (coins, sand) covered by the first book, and the upright ends in a small lip.
    """
    thickness = max(3, thickness)
    foot = cq.Workplane("XY").box(width, depth, thickness, centered=(True, False, False))
    upright = cq.Workplane("XY").box(width, thickness, height, centered=(True, False, False))
    top_lip = (
        cq.Workplane("XY")
        .box(width, lip + thickness, thickness, centered=(True, False, False))
        .translate((0, 0, height - thickness))
    )
    end = foot.union(upright).union(top_lip).edges("|X").fillet(min(2, thickness / 2.5))
    if weight_pocket > 0:
        pocket = (
            cq.Workplane("XY")
            .box(
                width - 2 * thickness,
                min(weight_pocket, depth - 2 * thickness),
                thickness - 1.2,
                centered=(True, False, False),
            )
            .translate((0, thickness, 1.2))
        )
        end = end.cut(pocket)
    return end
