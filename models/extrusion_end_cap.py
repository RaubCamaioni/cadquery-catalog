import cadquery as cq


def extrusion_end_cap(
    profile: float = 20,
    cap_thickness: float = 3,
    plug_depth: float = 6,
    bore_diameter: float = 4.2,
    corner_radius: float = 1.5,
) -> cq.Workplane:
    """An end cap for square aluminium extrusion (2020 by default, set 30 or 40 for larger): a flat
    cap with a plug that presses into the extrusion's centre bore.
    """
    cap = cq.Workplane("XY").rect(profile, profile).extrude(cap_thickness).edges("|Z").fillet(corner_radius)
    cap = cap.faces("<Z").edges().chamfer(min(1, cap_thickness / 3))
    plug = cq.Workplane("XY").workplane(offset=cap_thickness).circle(bore_diameter / 2 + 0.15).extrude(plug_depth)
    plug = plug.faces(">Z").chamfer(min(0.8, bore_diameter / 5))
    # a slit across the plug lets it compress for a snug fit
    slit = cq.Workplane("XY").workplane(offset=cap_thickness + 1.5).rect(bore_diameter + 2, 0.8).extrude(plug_depth)
    return cap.union(plug).cut(slit)
