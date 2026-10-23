import math
import cadquery as cq


def business_card_holder(
    card_width: float = 89,
    card_height: float = 51,
    stack_thickness: float = 12,
    angle: float = 70,
    wall: float = 3,
) -> cq.Workplane:
    """A desk holder that presents a stack of business cards leaning back at an angle."""
    angle = max(45, min(angle, 85))
    wall = max(2, wall)
    depth = stack_thickness + 2 * wall
    lean = card_height * math.cos(math.radians(angle))
    base = cq.Workplane("XY").box(card_width + 2 * wall, depth + lean + 10, wall, centered=(True, False, False))
    front = cq.Workplane("XY").box(card_width + 2 * wall, wall, card_height * 0.35, centered=(True, False, False))
    back = (
        cq.Workplane("XY")
        .box(card_width + 2 * wall, wall, card_height * 0.9, centered=(True, False, False))
        .rotate((0, 0, 0), (1, 0, 0), -(90 - angle))
        .translate((0, depth - wall, 0))
    )
    sides = (
        cq.Workplane("XY")
        .pushPoints([(-card_width / 2 - wall / 2, 0), (card_width / 2 + wall / 2, 0)])
        .rect(wall, depth)
        .extrude(card_height * 0.35)
        .translate((0, depth / 2, 0))
    )
    holder = base.union(front).union(back).union(sides)
    thumb = cq.Workplane("XY").center(0, 0).circle(card_width / 5).extrude(card_height).translate((0, -2, wall))
    return holder.cut(thumb)
