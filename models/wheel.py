import cadquery as cq


def wheel(
    diameter: float = 60,
    width: float = 20,
    bore: float = 5,
    bore_flat: float = 0,
    tire_groove: float = 4,
    spokes: int = 5,
    hub_diameter: float = 16,
) -> cq.Workplane:
    """A robot wheel: a rim with a groove for an O-ring or rubber band tire, a hub with a D-shaped
    bore (set bore_flat to the flat's depth, 0 for round) and open spokes.
    """
    spokes = max(0, min(spokes, 12))
    r = diameter / 2
    rim = cq.Workplane("XY").circle(r).extrude(width)
    if tire_groove > 0:
        groove = (
            cq.Workplane("XY")
            .workplane(offset=width / 2 - tire_groove / 2)
            .circle(r + 1)
            .circle(r - tire_groove / 2)
            .extrude(tire_groove)
        )
        rim = rim.cut(groove)
    rim_inner = r - max(tire_groove / 2 + 2, 4)
    hub_r = max(bore / 2 + 3, hub_diameter / 2)
    if spokes and rim_inner > hub_r + 4:
        ring = cq.Workplane("XY").circle(rim_inner).circle(hub_r).extrude(width)
        for i in range(spokes):
            spoke = (
                cq.Workplane("XY")
                .center(rim_inner / 2, 0)
                .rect(rim_inner, 4)
                .extrude(width)
                .rotate((0, 0, 0), (0, 0, 1), 360 * i / spokes)
            )
            ring = ring.cut(spoke)
        rim = rim.cut(ring)
    axle = cq.Workplane("XY").circle(bore / 2).extrude(width)
    if bore_flat > 0:
        axle = axle.cut(
            cq.Workplane("XY").center(bore / 2 + bore / 2 - bore_flat + bore / 2, 0).rect(bore, bore + 2).extrude(width)
        )
    return rim.cut(axle)
