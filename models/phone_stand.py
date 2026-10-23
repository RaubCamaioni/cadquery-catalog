import math
import cadquery as cq


def phone_stand(
    width: float = 80,
    angle: float = 65,
    slot_width: float = 12,
    lip_height: float = 10,
    back_height: float = 90,
    thickness: float = 8,
) -> cq.Workplane:
    """A desk stand: a leaning back plate with a slot and a lip that holds the phone or tablet."""
    angle = max(40, min(angle, 85))
    slot_width = max(4, slot_width)
    thickness = max(3, thickness)
    base_depth = slot_width + thickness * 2 + back_height * math.cos(math.radians(angle)) + 10
    base = cq.Workplane("XY").box(width, base_depth, thickness, centered=(True, False, False))
    # the back plate leans by `angle` from the base; it starts behind the slot
    back = (
        cq.Workplane("YZ")
        .center(slot_width + thickness * 1.5, thickness)
        .rect(thickness, back_height, centered=(True, False))
        .extrude(width / 2, both=True)
        .rotate(
            (slot_width + thickness * 1.5, 0, thickness), (slot_width + thickness * 1.5, 1, thickness), -(90 - angle)
        )
    )
    lip = cq.Workplane("XY").center(0, thickness / 2).rect(width, thickness).extrude(thickness + lip_height)
    stand = base.union(back).union(lip)
    # a cable channel through the base under the slot
    cable = cq.Workplane("XY").center(0, thickness + slot_width / 2).rect(12, slot_width).extrude(thickness)
    return stand.cut(cable)
