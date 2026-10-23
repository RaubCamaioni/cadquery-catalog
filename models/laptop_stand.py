import math
import cadquery as cq


def laptop_stand(
    width: float = 260,
    depth: float = 230,
    angle: float = 15,
    thickness: float = 6,
    lip_height: float = 12,
    side_rails: float = 20,
) -> cq.Workplane:
    """A wedge laptop stand: a tilted deck on two side rails with a lip at the front edge, open
    underneath for airflow.
    """
    angle = max(5, min(angle, 35))
    thickness = max(4, thickness)
    rise = depth * math.tan(math.radians(angle))
    rail = (
        cq.Workplane("YZ")
        .polyline([(0, 0), (depth, 0), (depth, rise + thickness), (0, thickness)])
        .close()
        .extrude(side_rails / 2, both=True)
    )
    rails = rail.translate((-width / 2 + side_rails / 2, 0, 0)).union(
        rail.translate((width / 2 - side_rails / 2, 0, 0))
    )
    deck = (
        cq.Workplane("XY")
        .box(width, math.hypot(depth, rise), thickness, centered=(True, False, False))
        .rotate((0, 0, 0), (1, 0, 0), angle)
        .translate((0, 0, 0))
    )
    lip = (
        cq.Workplane("XY")
        .box(width, thickness, lip_height + thickness, centered=(True, False, False))
        .rotate((0, 0, 0), (1, 0, 0), angle)
    )
    stand = rails.union(deck).union(lip)
    vent = (
        cq.Workplane("XY")
        .center(0, depth / 2)
        .rect(width - 2 * side_rails - 20, depth * 0.5)
        .extrude(rise + thickness + 5)
        .translate((0, 0, -1))
    )
    return stand.cut(vent.cut(deck.translate((0, 0, -0.5))))
