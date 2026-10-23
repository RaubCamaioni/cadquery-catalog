from pathlib import Path
from typing import Literal
import cadquery as cq
import numpy as np


def _heights(image: Path | None, cells: int) -> np.ndarray:
    """Brightness of the image on a cells x cells grid (0 dark .. 1 bright); a demo pattern without an image."""
    if image is None:
        y, x = np.mgrid[0:cells, 0:cells] / (cells - 1)
        ring = np.exp(-((np.hypot(x - 0.5, y - 0.5) - 0.3) ** 2) / 0.01)
        return np.clip(0.15 + 0.85 * ring, 0, 1)
    from PIL import Image

    with Image.open(image) as im:
        grey = im.convert("L")
        grey.thumbnail((cells, cells))  # keep the picture's proportions inside the grid
        frame = Image.new("L", (cells, cells), int(np.median(np.asarray(grey))))
        frame.paste(grey, ((cells - grey.width) // 2, (cells - grey.height) // 2))
        return np.asarray(frame, dtype=float)[::-1] / 255.0


def _loops(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    """Closed outlines of the filled cells of a mask, as lattice points. The filled side is kept on
    the left of each edge, so outer loops run counter-clockwise and holes clockwise.
    """
    padded = np.pad(mask, 1)
    edges = {}
    rows, cols = padded.shape
    for y in range(1, rows):
        for x in range(1, cols):
            here = padded[y, x]
            if here != padded[y - 1, x]:  # horizontal edge on the bottom side of this cell
                edges[(x - 1, y - 1)] = (x, y - 1) if here else None
                if not here:
                    edges[(x, y - 1)] = (x - 1, y - 1)
            if here != padded[y, x - 1]:  # vertical edge on the left side of this cell
                if here:
                    edges[(x - 1, y)] = (x - 1, y - 1)
                else:
                    edges[(x - 1, y - 1)] = (x - 1, y)
    loops = []
    while edges:
        start, nxt = next(iter(edges.items()))
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
    out = []
    n = len(loop)
    for i, p in enumerate(loop):
        a, b = loop[i - 1], loop[(i + 1) % n]
        if (a[0] == p[0] == b[0]) or (a[1] == p[1] == b[1]):
            continue  # collinear, drop it
        out.append(p)
    return out


def _area(loop) -> float:
    return 0.5 * sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1]))


def _inside(point, loop) -> bool:
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(loop, loop[1:] + loop[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def mask_solid(
    mask: np.ndarray, cell: float, origin: tuple[float, float], z: float, height: float
) -> cq.Workplane | None:
    """The filled cells of `mask` as one extruded region (outlines with holes), or None when empty."""
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
    if not solids:
        return None
    return cq.Workplane("XY").newObject(solids)


def image_relief(
    image: Path = None,
    width: float = 80,
    cells: int = 48,
    relief_depth: float = 4,
    base_thickness: float = 2,
    levels: int = 8,
    mode: Literal["relief", "lithophane"] = "relief",
) -> cq.Workplane:
    """A 2D depth map from a picture: the image is sampled on a grid and each cell rises with its
    brightness, in a chosen number of height levels. Relief raises the bright parts; lithophane
    raises the dark parts, so light shining through from behind shows the picture. Upload any
    image, or leave it empty to see the demo pattern.
    """
    cells = max(8, min(int(cells), 96))
    levels = max(2, min(int(levels), 32))
    heights = _heights(image, cells)
    if mode == "lithophane":
        heights = 1 - heights
    cell = width / cells
    origin = (-width / 2, -width / 2)
    result = cq.Workplane("XY").box(width, width, base_thickness, centered=(True, True, False))
    quantised = np.round(heights * (levels - 1)).astype(int)
    step = relief_depth / (levels - 1)
    for level in range(1, levels):
        # each layer starts a hair inside the one below, so the union fuses into one solid
        layer = mask_solid(quantised >= level, cell, origin, base_thickness + step * (level - 1) - 0.01, step + 0.01)
        if layer is not None:
            result = result.union(layer)
    return result
