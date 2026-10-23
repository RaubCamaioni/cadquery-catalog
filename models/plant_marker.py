import cadquery as cq


def plant_marker(
    tag_width: float = 60,
    tag_height: float = 25,
    stake_length: float = 80,
    thickness: float = 2.4,
    count: int = 6,
) -> cq.Workplane:
    """Garden markers: a flat tag on a pointed stake, several laid out together to print as a sheet.
    Write on the tag with a marker.
    """
    count = max(1, min(count, 20))
    thickness = max(1.2, thickness)
    stake_w = max(8, tag_width / 4)
    result = None
    for i in range(count):
        x = i * (tag_width + 6)
        tag = (
            cq.Workplane("XY")
            .box(tag_width, tag_height, thickness, centered=(False, False, False))
            .edges("|Z")
            .fillet(3)
        )
        stake = (
            cq.Workplane("XY")
            .polyline(
                [(tag_width / 2 - stake_w / 2, 0), (tag_width / 2 + stake_w / 2, 0), (tag_width / 2, -stake_length)]
            )
            .close()
            .extrude(thickness)
        )
        marker = tag.union(stake).translate((x, 0, 0))
        result = marker if result is None else result.union(marker)
    return result
