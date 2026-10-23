import cadquery as cq


def card_deck_box(
    card_width: float = 63.5,
    card_height: float = 88.9,
    deck_thickness: float = 20,
    wall: float = 1.6,
    thumb_cutout: float = 25,
) -> cq.Workplane:
    """An open-top box for a deck of cards, with a thumb cutout on the front (poker size by default;
    bridge cards are 57 x 88.9 mm, tarot 70 x 120 mm).
    """
    wall = max(1.2, wall)
    w, d, h = card_width + 1 + 2 * wall, deck_thickness + 1 + 2 * wall, card_height * 0.8
    box = cq.Workplane("XY").box(w, d, h, centered=(True, True, False)).edges("|Z").fillet(2)
    cavity = cq.Workplane("XY").workplane(offset=wall).rect(card_width + 1, deck_thickness + 1).extrude(h)
    thumb = cq.Workplane("XZ").center(0, h).circle(thumb_cutout / 2).extrude(d, both=True)
    return box.cut(cavity).cut(thumb)
