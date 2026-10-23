import cadquery as cq


def s_hook(
    height: float = 60,
    hook_diameter: float = 24,
    wire_diameter: float = 5,
    opening: float = 10,
) -> cq.Workplane:
    """An S-hook for hanging things from rails and baskets, printed flat: two C-shaped loops
    opening on opposite sides, joined by a straight middle when the height allows.
    """
    r = hook_diameter / 2
    w = wire_diameter
    stem = max(0.0, height - 4 * r)
    cy = r + stem / 2  # centre height of the upper loop
    upper = cq.Workplane("XY").center(0, cy).circle(r + w / 2).circle(r - w / 2).extrude(w)
    lower = cq.Workplane("XY").center(0, -cy).circle(r + w / 2).circle(r - w / 2).extrude(w)
    # each loop opens on the side away from the junction, just below (above) its equator
    gap_u = cq.Workplane("XY").center(r + w, cy - r / 2).rect(2 * r, opening).extrude(w)
    gap_l = cq.Workplane("XY").center(-r - w, -cy + r / 2).rect(2 * r, opening).extrude(w)
    hook = upper.cut(gap_u).union(lower.cut(gap_l))
    if stem > 0:
        hook = hook.union(cq.Workplane("XY").rect(w, stem + 0.2).extrude(w))
    return hook
