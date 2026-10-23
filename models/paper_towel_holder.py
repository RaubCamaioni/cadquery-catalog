import cadquery as cq


def paper_towel_holder(
    roll_height: float = 280,
    core_diameter: float = 40,
    base_diameter: float = 150,
    base_thickness: float = 10,
    post_diameter: float = 30,
) -> cq.Workplane:
    """A countertop paper towel holder: a weighted-looking base and a post the roll drops over."""
    post_diameter = max(10, min(post_diameter, core_diameter - 4))
    base = (
        cq.Workplane("XY")
        .circle(base_diameter / 2)
        .extrude(base_thickness)
        .faces(">Z")
        .edges()
        .fillet(min(4, base_thickness / 3))
    )
    post = cq.Workplane("XY").circle(post_diameter / 2).extrude(roll_height + base_thickness + 10)
    cap = (
        cq.Workplane("XY")
        .workplane(offset=roll_height + base_thickness + 10)
        .circle(post_diameter / 2)
        .workplane(offset=8)
        .circle(post_diameter / 4)
        .loft()
    )
    # hollow the post to save material; it stays closed at both ends
    core = cq.Workplane("XY").workplane(offset=base_thickness + 3).circle(post_diameter / 2 - 2.4).extrude(roll_height)
    return base.union(post).union(cap).cut(core)
