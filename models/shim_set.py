import cadquery as cq


def shim_set(
    width: float = 30,
    length: float = 40,
    thicknesses_mm: str = "0.5,1,1.5,2,3",
    hole_diameter: float = 6,
    gap: float = 5,
) -> cq.Workplane:
    """A set of flat shims of different thicknesses laid out side by side, each with a slot so it
    slides around a bolt.
    """
    try:
        sizes = [max(0.2, min(float(s), 20)) for s in thicknesses_mm.replace(";", ",").split(",") if s.strip()]
    except ValueError:
        sizes = [0.5, 1, 1.5, 2, 3]
    sizes = sizes[:12] or [1.0]
    result = None
    for i, t in enumerate(sizes):
        x = i * (width + gap)
        shim = cq.Workplane("XY").box(width, length, t, centered=(False, True, False)).translate((x, 0, 0))
        slot = (
            cq.Workplane("XY")
            .center(x + width / 2, length / 4)
            .slot2D(length / 2 + hole_diameter, hole_diameter, angle=90)
            .extrude(t)
        )
        shim = shim.cut(slot).edges("|Z").fillet(min(3, width / 6))
        result = shim if result is None else result.union(shim)
    return result
