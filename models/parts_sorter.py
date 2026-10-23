import cadquery as cq


def parts_sorter(
    compartments: int = 4,
    compartment_width: float = 40,
    depth: float = 60,
    front_height: float = 15,
    back_height: float = 40,
    wall: float = 1.6,
) -> cq.Workplane:
    """A sorting tray whose compartments slope from a low front to a high back, so small parts are
    easy to see and to pick out.
    """
    compartments = max(1, min(compartments, 12))
    wall = max(1, wall)
    width = compartments * (compartment_width + wall) + wall
    body = (
        cq.Workplane("YZ")
        .polyline([(0, 0), (depth, 0), (depth, back_height), (0, front_height)])
        .close()
        .extrude(width / 2, both=True)
    )
    for i in range(compartments):
        x = -width / 2 + wall + compartment_width / 2 + i * (compartment_width + wall)
        pocket = (
            cq.Workplane("YZ")
            .polyline([(wall, wall), (depth - wall, wall), (depth - wall, back_height + 1), (wall, front_height + 1)])
            .close()
            .extrude(compartment_width / 2, both=True)
            .translate((x, 0, 0))
        )
        body = body.cut(pocket)
    return body
