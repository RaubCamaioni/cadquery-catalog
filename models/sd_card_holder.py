from typing import Literal
import cadquery as cq

CARDS = {"sd": (24.2, 2.4), "microsd": (11.2, 1.1)}


def sd_card_holder(
    card: Literal["sd", "microsd"] = "sd",
    slots: int = 8,
    slot_depth: float = 12,
    pitch: float = 6,
    wall: float = 2,
) -> cq.Workplane:
    """A block with a row of slots that hold memory cards upright."""
    width, thickness = CARDS[card]
    slots = max(1, min(slots, 30))
    pitch = max(thickness + 1.5, pitch)
    length = slots * pitch + wall
    body = cq.Workplane("XY").box(length, width + wall * 2, slot_depth + wall, centered=(True, True, False))
    body = body.edges("|Z").fillet(min(2, wall)).faces(">Z").edges().chamfer(min(0.6, wall / 3))
    cuts = (
        cq.Workplane("XY")
        .workplane(offset=wall)
        .pushPoints([(-length / 2 + wall + pitch / 2 + i * pitch, 0) for i in range(slots)])
        .rect(thickness + 0.4, width + 0.4)
        .extrude(slot_depth + 1)
    )
    return body.cut(cuts)
