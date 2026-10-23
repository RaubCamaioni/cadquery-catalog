import cadquery as cq


def bowl(
    diameter: float = 120,
    height: float = 50,
    wall: float = 2.4,
    foot_diameter: float = 50,
    foot_height: float = 4,
    rim_roll: float = 3,
) -> cq.Workplane:
    """A revolved bowl with a flat foot ring and a rolled rim."""
    wall = max(1, min(wall, diameter / 12))
    foot_diameter = max(10, min(foot_diameter, diameter - 10))
    r, fr = diameter / 2, foot_diameter / 2
    profile = (
        cq.Workplane("XZ")
        .moveTo(0, foot_height)
        .lineTo(fr - wall, foot_height)
        .lineTo(fr - wall, 0)
        .lineTo(fr, 0)
        .threePointArc((r * 0.85, height * 0.55), (r, height))
        .lineTo(r - wall - rim_roll, height)
        .threePointArc((r * 0.85 - wall, height * 0.55 - wall / 2), (fr - wall + wall, foot_height + wall))
        .lineTo(0, foot_height + wall)
        .close()
    )
    body = profile.revolve(360, (0, 0, 0), (0, 1, 0))
    if rim_roll > 0:
        body = body.faces(">Z").edges().fillet(min(rim_roll / 2, wall / 2.1))
    return body
