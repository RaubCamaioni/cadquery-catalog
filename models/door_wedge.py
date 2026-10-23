import cadquery as cq


def door_wedge(
    length: float = 100,
    width: float = 35,
    height: float = 25,
    tip_height: float = 2,
    grip_ridges: int = 6,
) -> cq.Workplane:
    """A door stop or shim wedge with ridges on top for grip."""
    tip_height = max(0.6, min(tip_height, height / 2))
    grip_ridges = max(0, min(grip_ridges, 20))
    wedge = (
        cq.Workplane("YZ")
        .polyline([(0, 0), (length, 0), (length, tip_height), (0, height)])
        .close()
        .extrude(width / 2, both=True)
    )
    if grip_ridges:
        import math

        slope = math.atan2(height - tip_height, length)
        pitch = length / (grip_ridges + 1)
        for i in range(grip_ridges):
            y = pitch * (i + 1)
            z = height - (height - tip_height) * y / length
            ridge = (
                cq.Workplane("XY")
                .box(width, 1.6, 1.2, centered=(True, True, False))
                .rotate((0, 0, 0), (1, 0, 0), -math.degrees(slope))
                .translate((0, y, z - 0.3))
            )
            wedge = wedge.cut(ridge)
    return wedge
