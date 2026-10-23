import cadquery as cq


def drawer_divider(
    length: float = 300,
    height: float = 60,
    thickness: float = 3,
    foot_width: float = 20,
    foot_depth: float = 12,
    notches: int = 4,
) -> cq.Workplane:
    """A free-standing divider strip for a drawer: a thin wall on feet, with notches along the top so
    cross dividers of the same thickness can slot in.
    """
    thickness = max(1.6, thickness)
    notches = max(0, min(notches, 20))
    wall = cq.Workplane("XY").box(length, thickness, height, centered=(True, True, False))
    feet = (
        cq.Workplane("XY")
        .pushPoints([(-length / 2 + foot_width / 2 + 5, 0), (length / 2 - foot_width / 2 - 5, 0)])
        .rect(foot_width, foot_depth)
        .extrude(thickness)
    )
    divider = wall.union(feet)
    if notches:
        pitch = length / (notches + 1)
        slots = (
            cq.Workplane("XY")
            .workplane(offset=height / 2)
            .pushPoints([(-length / 2 + pitch * (i + 1), 0) for i in range(notches)])
            .rect(thickness + 0.4, foot_depth * 2)
            .extrude(height)
        )
        divider = divider.cut(slots)
    return divider.edges("|Y").fillet(min(1, thickness / 3))
