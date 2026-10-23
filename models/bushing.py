import cadquery as cq


def bushing(
    shaft_diameter: float = 8,
    outer_diameter: float = 12,
    length: float = 15,
    flange_diameter: float = 18,
    flange_thickness: float = 2,
    clearance: float = 0.2,
) -> cq.Workplane:
    """A flanged sleeve bushing: a plain bearing for a shaft (set flange_thickness to 0 for a plain
    sleeve). Print in a slippery filament such as nylon or PETG.
    """
    bore = shaft_diameter + clearance
    outer_diameter = max(bore + 2, outer_diameter)
    sleeve = cq.Workplane("XY").circle(outer_diameter / 2).extrude(length)
    if flange_thickness > 0:
        flange = cq.Workplane("XY").circle(max(flange_diameter, outer_diameter + 2) / 2).extrude(flange_thickness)
        sleeve = sleeve.union(flange)
    bushing_ = sleeve.cut(cq.Workplane("XY").circle(bore / 2).extrude(length))
    return bushing_.faces(">Z").edges().chamfer(min(0.6, (outer_diameter - bore) / 5))
