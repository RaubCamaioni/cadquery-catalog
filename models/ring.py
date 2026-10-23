import cadquery as cq


def ring(outer_radius: float = 12, inner_radius: float = 8, extrusion_height: float = 4) -> cq.Workplane:
    """A flat ring: a cylinder with a concentric hole."""
    inner_radius = min(inner_radius, outer_radius - 0.2)
    outer = cq.Workplane("XY").circle(outer_radius).extrude(extrusion_height)
    inner = cq.Workplane("XY").circle(inner_radius).extrude(extrusion_height)
    return outer.cut(inner)
