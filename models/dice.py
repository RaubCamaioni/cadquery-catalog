import cadquery as cq


def dice(
    size: float = 16,
    corner_radius: float = 2,
    pip_diameter: float = 3.2,
    pip_depth: float = 0.8,
) -> cq.Workplane:
    """A six-sided die with dimpled pips laid out so opposite faces sum to seven."""
    corner_radius = max(0.5, min(corner_radius, size / 3))
    pip_depth = max(0.3, min(pip_depth, pip_diameter / 2))
    cube = cq.Workplane("XY").box(size, size, size).edges().fillet(corner_radius)
    o = size * 0.27
    layouts = {
        1: [(0, 0)],
        2: [(-o, -o), (o, o)],
        3: [(-o, -o), (0, 0), (o, o)],
        4: [(-o, -o), (o, o), (-o, o), (o, -o)],
        5: [(-o, -o), (o, o), (-o, o), (o, -o), (0, 0)],
        6: [(-o, -o), (o, o), (-o, o), (o, -o), (-o, 0), (o, 0)],
    }
    # face number -> (normal, in-plane u axis, in-plane v axis); opposite faces sum to seven
    frames = {
        1: ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
        6: ((0, 0, -1), (1, 0, 0), (0, 1, 0)),
        2: ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
        5: ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
        3: ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        4: ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
    }
    rr = pip_diameter / 2
    lift = size / 2 + rr - pip_depth  # a dimple is a sphere whose centre sits just outside the face
    pips = []
    for n, (nrm, u, v) in frames.items():
        for px, py in layouts[n]:
            c = tuple(nrm[i] * lift + u[i] * px + v[i] * py for i in range(3))
            pips.append(cq.Solid.makeSphere(rr, cq.Vector(*c)))
    return cube.cut(cq.Workplane("XY").newObject(pips))
