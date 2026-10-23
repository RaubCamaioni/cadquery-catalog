"""Build every sample model with its defaults inside the sandbox image, and check that the kitchen
measuring models hold what they say they hold.

Run it with ./test_models.sh from the repository root. It is local only: CI builds the sandbox image
but never runs the models.

    check_models.py                      every model, then the kitchen checks
    check_models.py measuring_cup ...    only the named models (their kitchen checks included)
"""

import importlib.util
import math
import sys
import tempfile
import time
import traceback
from pathlib import Path

import cadquery as cq

from sandbox.export import export_model, to_shape

MODELS = Path(__file__).resolve().parents[2] / "models"
SLOW_SECONDS = 8  # the sandbox allows 10 s per run, cold start included
FAILURES = []


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, MODELS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build(name: str, **kwargs):
    return to_shape(getattr(load(name), name)(**kwargs))


def check(label: str, condition: bool, detail: str = ""):
    print(f"  {'ok  ' if condition else 'FAIL'} {label}{(': ' + detail) if detail else ''}")
    if not condition:
        FAILURES.append(f"{label}: {detail}")


def water_ml(shape: cq.Shape, level: float, axis=(0.0, 0.0)) -> float:
    """What the solid holds below z = level, in ml: fill its bounding box up to the level, cut the solid
    away, and keep the pocket on the axis. Measured on the finished solid, not on the model's own maths."""
    bb = shape.BoundingBox()
    box = cq.Solid.makeBox(bb.xlen + 20, bb.ylen + 20, level - bb.zmin + 1, pnt=cq.Vector(bb.xmin - 10, bb.ymin - 10, bb.zmin - 1))
    # the air outside reaches the sides of the box; a pocket the solid holds does not
    pockets = [s for s in box.cut(shape).Solids() if s.BoundingBox().xmin > bb.xmin - 9]
    pockets = [s for s in pockets if s.BoundingBox().xmin < axis[0] < s.BoundingBox().xmax]
    return max((s.Volume() for s in pockets), default=0.0) / 1000


def printable(name: str, shape: cq.Shape):
    """Printed as modelled: every solid stands on a flat face on the bed, and almost nothing above the
    bed faces down more steeply than 50 degrees from vertical (raised lettering is allowed its small
    ledges). Labels belong on top faces and walls, never on the face against the bed."""
    bed = shape.BoundingBox().zmin
    for i, solid in enumerate(shape.Solids()):
        base = [f for f in solid.Faces() if f.geomType() == "PLANE" and abs(f.BoundingBox().zmax - bed) < 1e-3]
        largest = max((f.Area() for f in base), default=0)
        check(f"{name}: solid {i} stands on a flat face on the bed", largest >= 100, f"{largest:.0f} mm^2")
    verts, tris = shape.tessellate(0.05, 0.3)
    down = total = 0.0
    for a, b, c in tris:
        A, B, C = verts[a], verts[b], verts[c]
        n = (B - A).cross(C - A)
        area = n.Length / 2
        total += area
        if area and n.z / n.Length < -math.cos(math.radians(40)) and min(A.z, B.z, C.z) > bed + 0.2:
            down += area
    check(f"{name}: no steep overhangs", down <= 0.01 * total, f"{down:.0f} of {total:.0f} mm^2 faces down")


def close(actual: float, expected: float, rel: float = 0.01) -> bool:
    return abs(actual - expected) <= rel * expected


def every_model(names):
    print(f"building {len(names)} models with their defaults")
    for name in names:
        start = time.perf_counter()
        try:
            shape = build(name)
            with tempfile.TemporaryDirectory() as tmp:
                export_model(shape, Path(tmp))
            elapsed = time.perf_counter() - start
            # export is the bar, not isValid(): models built from a mesh (image_relief, stl_coaster) are
            # never valid B-reps by OCCT's checker, yet export and print fine
            check(f"{name} builds and exports", elapsed < SLOW_SECONDS, f"{elapsed:.1f} s")
        except Exception:
            check(f"{name} builds and exports", False, traceback.format_exc(limit=2).strip().splitlines()[-1])


def measuring_cup():
    module = load("measuring_cup")
    cases = [
        dict(),  # 1 cup, quarter and third markers
        dict(capacity=500, unit="ml", markers="100, 200, 250, 300, 400"),
        dict(capacity=2, unit="tbsp", markers="1/2, 1, 1 1/2"),
        dict(capacity=1, unit="cup", markers="50, 100, 150, 200", marker_unit="ml"),
        dict(capacity=1, unit="metric_cup", markers="", headroom=0),
    ]
    for kwargs in cases:
        shape = build("measuring_cup", **kwargs)
        printable(f"measuring_cup {kwargs or 'defaults'}", shape)
        for text, ml, z, grooved in module.marker_levels(**kwargs):
            got = water_ml(shape, z)
            check(f"measuring_cup {kwargs or 'defaults'} holds {text} at its line", close(got, ml), f"{got:.2f} ml, want {ml:.2f} ml")
            if grooved:  # a dry cup's capacity is its brim, not a line
                # the line is a groove in the inside wall at that height
                # its flat lower edge is the line, with a 45 degree roof above so it needs no support
                r = module.inner_radius_at(z, **kwargs)
                check(f"measuring_cup {kwargs or 'defaults'} has a groove at {text}", not shape.isInside(cq.Vector(0, r + 0.25, z + 0.1)))
    for bad in ("2", "abc", "-1", "1/0"):
        try:
            build("measuring_cup", markers=bad)
            check(f"measuring_cup refuses markers={bad!r}", False, "built anyway")
        except ValueError:
            check(f"measuring_cup refuses markers={bad!r}", True)


def measuring_scoop():
    for kwargs, ml in ((dict(), 30), (dict(volume=1, unit="tbsp"), 14.7868), (dict(volume=0.25, unit="cup"), 59.147)):
        shape = build("measuring_scoop", **kwargs)
        printable(f"measuring_scoop {kwargs or 'defaults'}", shape)
        # just under the brim (its highest vertex: a bounding box pads out once the shape is tessellated);
        # at the rim plane itself the bowl and the air around it share a face
        got = water_ml(shape, max(v.Z for v in shape.Vertices()) - 0.01)
        check(f"measuring_scoop {kwargs or 'defaults'} holds {ml:.2f} ml to the brim", close(got, ml), f"{got:.2f} ml")


def spaghetti_measure():
    module = load("spaghetti_measure")
    shape = build("spaghetti_measure", servings=4)
    printable("spaghetti_measure", shape)
    diameters = [module.hole_diameter(n) for n in range(1, 5)]
    check("spaghetti_measure: one serving of 85 g is a 17-23 mm hole", 17 <= diameters[0] <= 23, f"{diameters[0]:.1f} mm")
    for n, d in enumerate(diameters, start=1):
        check(f"spaghetti_measure: hole area grows with servings ({n})", close(d, diameters[0] * math.sqrt(n), 0.001))
    for (x, y), d in zip(module.hole_centres(4), diameters):
        inside_hole = not shape.isInside(cq.Vector(x + d / 2 * 0.97, y, 1))
        in_plate = shape.isInside(cq.Vector(x + d / 2 * 1.03 + 0.2, y, 1))
        check(f"spaghetti_measure: hole of {d:.1f} mm is cut to size", inside_hole and in_plate)


def rolling_pin_guides():
    shape = build("rolling_pin_guides", pin_diameter=50, thicknesses="3, 5", clearance=0.4)
    printable("rolling_pin_guides", shape)
    rings = sorted(shape.Solids(), key=lambda s: s.BoundingBox().xlen)
    check("rolling_pin_guides: a pair of rings per thickness", len(rings) == 4, f"{len(rings)} solids")
    for ring, t in zip(rings, (3, 3, 5, 5)):
        c = ring.BoundingBox().center
        # the pin rests on the bottom of the bore, so the dough is (outside - bore) / 2 thick
        rim = 50.4 / 2 + t
        outside = ring.isInside(cq.Vector(c.x + rim - 0.05, c.y, c.z)) and not ring.isInside(cq.Vector(c.x + rim + 0.05, c.y, c.z))
        check(f"rolling_pin_guides: {t} mm ring is the bore plus twice the thickness across", outside)
        bore = not ring.isInside(cq.Vector(c.x + 25.2 - 0.05, c.y, c.z)) and ring.isInside(cq.Vector(c.x + 25.2 + 0.1, c.y, c.z))
        check(f"rolling_pin_guides: {t} mm ring has a {50.4} mm bore", bore)


KITCHEN = {
    "measuring_cup": measuring_cup,
    "measuring_scoop": measuring_scoop,
    "spaghetti_measure": spaghetti_measure,
    "rolling_pin_guides": rolling_pin_guides,
}


def main(args):
    names = args or sorted(p.stem for p in MODELS.glob("*.py"))
    every_model(names)
    for name in names:
        if name in KITCHEN:
            print(f"checking {name}")
            try:
                KITCHEN[name]()
            except Exception:
                check(f"{name} checks ran", False, traceback.format_exc(limit=3).strip().splitlines()[-1])
    print(f"\n{len(FAILURES)} failure(s)" if FAILURES else "\nall checks passed")
    for failure in FAILURES:
        print(f"  {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
