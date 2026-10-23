from typing import Literal
import cadquery as cq


def pulley(
    diameter: float = 40,
    width: float = 10,
    bore: float = 8,
    groove: Literal["round", "v", "flat"] = "round",
    groove_depth: float = 3,
    hub_diameter: float = 16,
    hub_height: float = 6,
) -> cq.Workplane:
    """A belt pulley with a round, V or flat groove, a bore and an optional hub. Built as one
    revolved profile, so any combination of sizes stays valid.
    """
    diameter = max(bore + 10, diameter)
    width = max(3, width)
    groove_depth = max(0.5, min(groove_depth, (diameter - bore) / 4 - 0.5, width / 2 - 0.5))
    r, w, g = diameter / 2, width, groove_depth
    profile = cq.Workplane("XZ").moveTo(bore / 2, 0).lineTo(r, 0)
    if groove == "round":
        profile = profile.lineTo(r, w / 2 - g).threePointArc((r - g, w / 2), (r, w / 2 + g))
    elif groove == "v":
        profile = profile.lineTo(r, w / 2 - g).lineTo(r - g, w / 2).lineTo(r, w / 2 + g)
    else:
        flat = max(1, w - 2 * min(2, w / 4))
        profile = (
            profile.lineTo(r, (w - flat) / 2)
            .lineTo(r - g, (w - flat) / 2)
            .lineTo(r - g, (w + flat) / 2)
            .lineTo(r, (w + flat) / 2)
        )
    hub_r = hub_diameter / 2 if (hub_height > 0 and hub_diameter > bore + 2) else bore / 2
    top = w + (hub_height if hub_r > bore / 2 else 0)
    profile = profile.lineTo(r, w)
    if hub_r > bore / 2:
        profile = profile.lineTo(hub_r, w).lineTo(hub_r, top)
    profile = profile.lineTo(bore / 2, top).close()
    return profile.revolve(360, (0, 0, 0), (0, 1, 0))
