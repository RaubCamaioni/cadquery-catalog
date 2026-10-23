import cadquery as cq


def cord_cover(
    length: float = 300,
    cable_diameter: float = 8,
    cables: int = 2,
    ramp: float = 20,
    wall: float = 2,
) -> cq.Workplane:
    """A floor cord cover: a low ramp on both sides with channels for the cables underneath."""
    cables = max(1, min(cables, 6))
    wall = max(1.2, wall)
    channel_w = cable_diameter + 1
    inner_w = cables * channel_w + (cables - 1) * wall
    top_w = inner_w + 2 * wall
    width = top_w + 2 * ramp
    height = cable_diameter + 1 + wall
    profile = (
        cq.Workplane("YZ")
        .polyline([(-width / 2, 0), (width / 2, 0), (top_w / 2, height), (-top_w / 2, height)])
        .close()
    )
    cover = profile.extrude(length / 2, both=True)
    for i in range(cables):
        y = -inner_w / 2 + channel_w / 2 + i * (channel_w + wall)
        channel = (
            cq.Workplane("YZ").center(y, 0).rect(channel_w, 2 * (cable_diameter + 1)).extrude(length / 2 + 1, both=True)
        )
        cover = cover.cut(channel)
    return cover
