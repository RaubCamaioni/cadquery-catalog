import cadquery as cq


def servo_bracket(
    body_length: float = 23,
    body_width: float = 12.5,
    tab_spacing: float = 28,
    tab_screw: float = 2,
    wall: float = 3,
    height: float = 20,
    base_holes: float = 3.2,
) -> cq.Workplane:
    """A U-bracket for a micro servo (SG90 size by default; set 40.5 x 20 x 48.5 for a standard
    servo): the servo drops in from above and screws through its tabs into the bracket ends.
    """
    wall = max(2, wall)
    length = tab_spacing + 2 * wall + 6
    bracket = cq.Workplane("XY").box(length, body_width + 2 * wall, height, centered=(True, True, False))
    pocket = cq.Workplane("XY").workplane(offset=wall).rect(body_length + 0.6, body_width + 0.6).extrude(height)
    bracket = bracket.cut(pocket)
    # the tab region is open above the ends so the servo tabs rest on the ends
    tabs = cq.Workplane("XY").workplane(offset=height - 2.5).rect(tab_spacing + 6, body_width + 0.6).extrude(3)
    bracket = bracket.cut(tabs)
    screws = (
        cq.Workplane("XY")
        .workplane(offset=height - 8)
        .pushPoints([(-tab_spacing / 2, 0), (tab_spacing / 2, 0)])
        .circle(tab_screw / 2 * 0.9)
        .extrude(8)
    )
    bracket = bracket.cut(screws)
    feet = cq.Workplane("XY").box(length + 16, body_width + 2 * wall, wall, centered=(True, True, False))
    holes = (
        cq.Workplane("XY").pushPoints([(-length / 2 - 4, 0), (length / 2 + 4, 0)]).circle(base_holes / 2).extrude(wall)
    )
    return bracket.union(feet).cut(holes)
