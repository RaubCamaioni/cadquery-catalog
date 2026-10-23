from pathlib import Path
from typing import Literal
import struct
import cadquery as cq
import numpy as np


def _triangles(stl: Path) -> np.ndarray:
    """Vertices of every triangle in an STL file, binary or ASCII, as an (n, 3, 3) array."""
    data = stl.read_bytes()
    if data[:5].lower() != b"solid" or b"facet" not in data[:300]:
        count = struct.unpack("<I", data[80:84])[0]
        records = np.frombuffer(
            data[84 : 84 + count * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")])
        )
        return records["v"].reshape(-1, 3, 3).astype(float)
    verts = []
    for line in data.decode(errors="ignore").splitlines():
        parts = line.split()
        if parts[:1] == ["vertex"] and len(parts) == 4:
            verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
    verts = np.array(verts, dtype=float)
    return verts[: len(verts) // 3 * 3].reshape(-1, 3, 3)


def _footprint(stl: Path | None, cells: int) -> np.ndarray:
    """The mesh seen from above as a cells x cells mask (True where the model is); a star without a file."""
    y, x = np.mgrid[0:cells, 0:cells]
    cx, cy = (x + 0.5) / cells - 0.5, (y + 0.5) / cells - 0.5
    if stl is None:
        angle = np.arctan2(cy, cx)
        return np.hypot(cx, cy) < 0.22 + 0.2 * np.cos(5 * angle)
    tri = _triangles(stl)
    if len(tri) == 0:
        return np.zeros((cells, cells), dtype=bool)
    xy = tri[:, :, :2]
    lo, hi = xy.min(axis=(0, 1)), xy.max(axis=(0, 1))
    span = max(hi - lo) * 1.02
    centre = (lo + hi) / 2
    px, py = cx * span + centre[0], cy * span + centre[1]
    mask = np.zeros((cells, cells), dtype=bool)
    for a, b, c in xy:  # point-in-triangle by the signs of the edge functions, vectorised over the grid
        d1 = (px - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (py - b[1])
        d2 = (px - c[0]) * (b[1] - c[1]) - (b[0] - c[0]) * (py - c[1])
        d3 = (px - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (py - a[1])
        mask |= ~(((d1 < 0) | (d2 < 0) | (d3 < 0)) & ((d1 > 0) | (d2 > 0) | (d3 > 0)))
    return mask


def _loops(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """Closed outlines of the filled cells, filled side on the left: outers counter-clockwise, holes clockwise."""
    padded = np.pad(mask, 1)
    edges = {}
    rows, cols = padded.shape
    for y in range(1, rows):
        for x in range(1, cols):
            here = padded[y, x]
            if here != padded[y - 1, x]:
                if here:
                    edges[(x - 1, y - 1)] = (x, y - 1)
                else:
                    edges[(x, y - 1)] = (x - 1, y - 1)
            if here != padded[y, x - 1]:
                if here:
                    edges[(x - 1, y)] = (x - 1, y - 1)
                else:
                    edges[(x - 1, y - 1)] = (x - 1, y)
    loops = []
    while edges:
        start = next(iter(edges))
        loop, cur = [start], start
        while True:
            nxt = edges.pop(cur, None)
            if nxt is None or nxt == start:
                break
            loop.append(nxt)
            cur = nxt
        if len(loop) >= 4:
            loops.append(loop)
    return loops


def _simplify(loop):
    n = len(loop)
    return [
        p
        for i, p in enumerate(loop)
        if not ((loop[i - 1][0] == p[0] == loop[(i + 1) % n][0]) or (loop[i - 1][1] == p[1] == loop[(i + 1) % n][1]))
    ]


def _area(loop) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1]))


def _inside(point, loop) -> bool:
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def mask_solid(mask, cell, origin, z, height):
    """The filled cells of `mask` as extruded outline regions with holes, or None when empty."""
    loops = [_simplify(l) for l in _loops(mask)]
    outers = [l for l in loops if _area(l) > 0]
    holes = [l for l in loops if _area(l) < 0]
    to_xy = lambda p: (origin[0] + p[0] * cell, origin[1] + p[1] * cell)
    solids = []
    for outer in sorted(outers, key=_area):
        mine = [h for h in holes if _inside(h[0], outer)]
        holes = [h for h in holes if h not in mine]
        face = cq.Face.makeFromWires(
            cq.Wire.makePolygon([cq.Vector(*to_xy(p), z) for p in outer], close=True),
            [cq.Wire.makePolygon([cq.Vector(*to_xy(p), z) for p in h], close=True) for h in mine],
        )
        solids.append(cq.Solid.extrudeLinear(face, cq.Vector(0, 0, height)))
    return cq.Workplane("XY").newObject(solids) if solids else None


def stl_coaster(
    stl: Path = None,
    diameter: float = 95,
    thickness: float = 6,
    emboss: float = 1.5,
    cells: int = 64,
    shape: Literal["round", "square"] = "round",
) -> cq.Workplane:
    """A coaster with the top-down silhouette of an STL model embossed on it: upload any STL and
    its footprint is raised as a relief. Without a file, a star is embossed.
    """
    cells = max(12, min(int(cells), 128))
    mask = _footprint(stl, cells)
    if shape == "square":
        base = cq.Workplane("XY").rect(diameter, diameter).extrude(thickness).edges("|Z").fillet(min(6, diameter / 10))
    else:
        base = cq.Workplane("XY").circle(diameter / 2).extrude(thickness)
        # keep the relief inside the rim of a round coaster
        yy, xx = np.mgrid[0:cells, 0:cells]
        mask &= np.hypot((xx + 0.5) / cells - 0.5, (yy + 0.5) / cells - 0.5) < 0.5 * (diameter - 6) / (diameter * 0.8)
    size = diameter * 0.8
    relief = mask_solid(mask, size / cells, (-size / 2, -size / 2), thickness - 0.01, emboss + 0.01)
    return base.union(relief) if relief is not None else base
