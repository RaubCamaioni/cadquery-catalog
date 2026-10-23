import cadquery as cq


def hex_key_holder(
    sizes_mm: str = "1.5,2,2.5,3,4,5,6,8,10",
    depth: float = 25,
    spacing: float = 8,
    base_height: float = 30,
) -> cq.Workplane:
    """A block with a hole for each hex key in the set, sized from a list of across-flats sizes."""
    try:
        sizes = [max(0.5, min(float(s), 20)) for s in sizes_mm.replace(";", ",").split(",") if s.strip()]
    except ValueError:
        sizes = [1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]
    sizes = sizes[:20] or [3.0]
    depth = min(depth, base_height - 3)
    xs, x = [], 4.0
    for s in sizes:
        x += s / 2 + spacing / 2
        xs.append(x)
        x += s / 2 + spacing / 2
    length = x + 4
    block = (
        cq.Workplane("XY")
        .box(length, max(sizes) + 10, base_height, centered=(False, True, False))
        .edges("|Z")
        .fillet(2)
    )
    for s, cx in zip(sizes, xs):
        hole = (
            cq.Workplane("XY")
            .workplane(offset=base_height - depth)
            .center(cx, 0)
            .polygon(6, (s + 0.4) / 0.8660254)
            .extrude(depth)
        )
        block = block.cut(hole)
    return block
