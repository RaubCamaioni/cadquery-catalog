import cadquery as cq

NUTS = {
    "M3": (5.5, 2.4, 3.2),
    "M4": (7.0, 3.2, 4.3),
    "M5": (8.0, 4.7, 5.3),
    "M6": (10.0, 5.2, 6.4),
    "M8": (13.0, 6.8, 8.4),
}


def nut_trap_block(
    nut: str = "M4",
    length: float = 40,
    width: float = 20,
    height: float = 15,
    traps: int = 2,
) -> cq.Workplane:
    """A block with captive hex nut pockets and matching bolt holes, for joining printed parts.
    Nut sizes: M3, M4, M5, M6, M8.
    """
    flats, nut_h, bolt = NUTS.get(nut.upper().strip(), NUTS["M4"])
    traps = max(1, min(traps, 8))
    block = cq.Workplane("XY").box(length, width, height, centered=(True, True, False)).edges("|Z").fillet(2)
    pitch = length / (traps + 1)
    points = [(-length / 2 + pitch * (i + 1), 0) for i in range(traps)]
    pockets = (
        cq.Workplane("XY")
        .workplane(offset=height / 2 - nut_h / 2)
        .pushPoints(points)
        .polygon(6, (flats + 0.3) / 0.8660254)
        .extrude(nut_h + 0.3)
    )
    # the pocket opens to one side so the nut slides in
    slides = (
        cq.Workplane("XY")
        .workplane(offset=height / 2 - nut_h / 2)
        .pushPoints([(x, width / 4) for x, _ in points])
        .rect(flats + 0.3, width / 2)
        .extrude(nut_h + 0.3)
    )
    bolts = cq.Workplane("XY").pushPoints(points).circle(bolt / 2).extrude(height)
    return block.cut(pockets).cut(slides).cut(bolts)
