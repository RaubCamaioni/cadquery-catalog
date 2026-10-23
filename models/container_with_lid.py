from cadquery.occ_impl import shapes as occ_shapes
import cadquery as cq
import numpy as np


def loft_faces(f1: occ_shapes.Face, f2: occ_shapes.Face) -> occ_shapes.Solid:
    solid = cq.Solid.makeLoft([f1.outerWire(), f2.outerWire()])

    for inner1, inner2 in zip(f1.innerWires(), f2.innerWires()):
        solid_inner = cq.Solid.makeLoft([inner1, inner2])
        solid = solid.cut(solid_inner)

    return solid


def container(
    width,
    depth,
    height,
    thickness,
    ledge,
    exterior_ledge,
    fillet,
    angle,
    clearance,
    ridge,
):
    radians = np.deg2rad(angle)
    throw = depth * np.arctan(radians)
    height = height + throw / 2

    # create base box
    outer = cq.Workplane("XY").rect(width, depth).extrude(height)
    inner = (
        cq.Workplane("XY")
        .rect(width - thickness * 2, depth - thickness * 2)
        .extrude(height)
        .translate([0, 0, thickness])
    )
    box = outer.cut(inner)

    # cut angle
    if radians > 0:
        side_cut = (
            outer.faces(">X")
            .workplane()
            .moveTo(depth / 2, height)
            .lineTo(-depth / 2, height - throw)
            .lineTo(-depth / 2, height)
            .close()
            .extrude(-width, combine=False)
        )
        box = box.cut(side_cut)

    # cut ledge
    ledge_face = box.faces(">Z").val()
    outer_wire = ledge_face.outerWire()
    inner_wire = ledge_face.innerWires()[0]

    if exterior_ledge:
        tolerance_thickness = thickness - clearance
        offset_wire = inner_wire.offset2D(tolerance_thickness / 2)[0]
        cut_face = occ_shapes.Face.makeFromWires(outer_wire, [offset_wire])
    else:
        tolerance_thickness = thickness + clearance
        offset_wire = inner_wire.offset2D(tolerance_thickness / 2)[0]
        cut_face = occ_shapes.Face.makeFromWires(offset_wire, [inner_wire])
    cut_solid = loft_faces(cut_face, cut_face.translate([0, 0, -ledge]))

    # fillet vertical edges
    box = box.cut(cq.Workplane(obj=cut_solid)).edges("|Z").fillet(fillet)

    # fillet mating edges
    normal = cq.Vector(0, -np.sin(radians), np.cos(radians))
    box = (
        box.cut(cq.Workplane(obj=cut_solid))
        .faces(cq.selectors.ParallelDirSelector(normal, tolerance=0.1))
        .faces(cq.selectors.AreaNthSelector(0))
        .edges(cq.selectors.LengthNthSelector(0))
        .fillet(thickness / 4)
    )

    # extrude retention ridge
    edge: cq.Edge
    for edge in offset_wire.edges():
        if not edge.geomType() == "LINE":
            continue
        tangent: cq.Vector = edge.Center() - offset_wire.Center()
        tangent.z = 0
        x_dir = edge.positionAt(0.45) - edge.positionAt(0.55)

        upward_direction = cq.Vector(0, 0, 1)
        cross_product = tangent.cross(upward_direction)
        if not cross_product.dot(x_dir) < 0:
            x_dir = -x_dir

        plane = cq.Plane(
            origin=edge.Center(),
            xDir=x_dir,
            normal=tangent,
        )

        plane2 = plane.rotated(cq.Vector(0, 1, 0) * -90)

        a = ridge
        b = ledge / 8

        arc = (
            cq.Workplane(plane2)
            .moveTo(-thickness / 4, -b)
            .lineTo(0, -b)
            .ellipseArc(a, b, -90, 90, startAtCurrent=True)
            .lineTo(-thickness / 4, b)
            .close()
        )

        arc = arc.extrude(edge.Length() / 2 - 2, both=True)
        arc = arc.translate(-cq.Vector(0, 0, 1) * ledge / 2.0)

        if exterior_ledge:
            box = box.union(arc)
        else:
            box = box.cut(arc)

    return box.val()


def container_with_lid(
    width: float = 20.0,
    depth: float = 20.0,
    height: float = 20.0,
    thickness: float = 2.0,
    ledge: float = 5.0,
    fillet: float = 2.0,
    angle: float = 5.0,
    clearance: float = 0.1,
    top_ratio: float = 0.3,
    ridge_top: float = 2.0,
    ridge_bot: float = 3.0,
) -> cq.Workplane:
    """A box and its lid side by side; the lid's ledge slips over the box and a ridge holds it."""
    width = width + thickness * 2
    depth = depth + thickness * 2
    height = height + thickness * 2 + ledge
    lower_height = height * (1 - top_ratio)
    upper_height = height * top_ratio
    ledge = ledge
    fillet = fillet
    angle = angle
    clearance = clearance
    ridge_top = clearance * ridge_top
    ridge_bot = clearance * ridge_bot

    lower = container(
        width,
        depth,
        lower_height,
        thickness,
        ledge,
        True,
        fillet,
        angle,
        clearance,
        ridge_bot,
    )

    higher = (
        container(
            width,
            depth,
            upper_height,
            thickness,
            ledge,
            False,
            fillet,
            angle,
            clearance,
            ridge_top,
        )
        .rotate([0, 0, 0], [0, 0, 1], 0)
        .translate([width * 1.2, 0, 0])
    )

    return cq.Workplane(obj=cq.Compound.makeCompound([lower, higher]))
