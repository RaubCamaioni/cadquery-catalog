"""Turn the CadQuery object a model returns into the files the site serves.

A model's entrypoint returns a `cq.Workplane`, `cq.Shape` or `cq.Assembly`. From it this
module writes, into the current working directory (the run directory):

- `model.stl`   for the viewer and download
- `model.step`  for download
- `preview.svg` a line-drawing projection used as the thumbnail (no GPU or display needed)
- `meta.json`   bounding box, volume, surface area and solid count

and returns a dict of those paths plus the metadata, which becomes the run's result.
"""

from pathlib import Path
from typing import Any
import json
import re

# white strokes: the site draws thumbnails on a black background. The projection direction is
# CadQuery's default, which looks down onto the part from above-front with Z up; other
# directions came out mirrored or upside down.
SVG_OPTIONS = {
    "width": 480,
    "height": 360,
    "marginLeft": 24,
    "marginTop": 24,
    "showAxes": False,
    "projectionDir": (-1.75, 1.1, 5.0),
    "strokeWidth": 0.6,
    "strokeColor": (255, 255, 255),
    "hiddenColor": (90, 90, 90),
    "showHidden": False,
}
PREVIEW_MARGIN = 0.06  # of the drawing's size, on every side


class NotAModel(TypeError):
    """The entrypoint did not return a CadQuery object."""


def to_shape(result: Any):
    """A single `cq.Shape` from whatever the entrypoint returned."""
    import cadquery as cq

    if isinstance(result, cq.Assembly):
        return result.toCompound()
    if isinstance(result, cq.Workplane):
        shapes = [v for v in result.vals() if isinstance(v, cq.Shape)]
        if not shapes:
            raise NotAModel("the Workplane holds no shape (did the model forget to extrude?)")
        return shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
    if isinstance(result, cq.Shape):
        return result
    raise NotAModel(
        f"a model must return a cadquery Workplane, Shape or Assembly, not {type(result).__name__}"
    )


def measure(shape) -> dict:
    box = shape.BoundingBox()
    return {
        "size_mm": [round(box.xlen, 3), round(box.ylen, 3), round(box.zlen, 3)],
        "volume_mm3": round(shape.Volume(), 3),
        "area_mm2": round(shape.Area(), 3),
        "solids": len(shape.Solids()),
    }


_TRANSFORM = re.compile(r'transform="scale\(([-\d.e]+),\s*([-\d.e]+)\)\s*translate\(([-\d.e]+),\s*([-\d.e]+)\)"')
_NUMBER = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def fit_svg(svg: str) -> str:
    """Centre the drawing: CadQuery's exporter fits the part's 3D box, not the lines it drew,
    so the picture sits off-centre. Compute the extent of the drawn lines in page units and
    set a viewBox around them; the fixed width/height go, so the image scales to its box.
    """
    transform = _TRANSFORM.search(svg)
    paths = re.findall(r'd="([^"]+)"', svg)
    if transform is None or not paths:
        return svg
    sx, sy, tx, ty = (float(v) for v in transform.groups())
    xs, ys = [], []
    for d in paths:
        numbers = [float(n) for n in _NUMBER.findall(d)]
        xs.extend(sx * (x + tx) for x in numbers[0::2])
        ys.extend(sy * (y + ty) for y in numbers[1::2])
    if not xs or not ys:
        return svg
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    m = PREVIEW_MARGIN * max(w, h)
    view_box = f'viewBox="{x0 - m:.3f} {y0 - m:.3f} {w + 2 * m:.3f} {h + 2 * m:.3f}"'
    svg = re.sub(r'\s+width="[^"]*"', "", svg, count=1)
    svg = re.sub(r'\s+height="[^"]*"', "", svg, count=1)
    return svg.replace("<svg\n", f"<svg\n   {view_box}\n", 1) if "<svg\n" in svg else svg.replace("<svg", f"<svg {view_box}", 1)


def export_model(result: Any, workdir: Path | None = None) -> dict:
    from cadquery import exporters

    workdir = Path(workdir or Path.cwd())
    shape = to_shape(result)
    files = {name: workdir / name for name in ("model.stl", "model.step", "preview.svg")}
    exporters.export(shape, str(files["model.stl"]))
    exporters.export(shape, str(files["model.step"]))
    exporters.export(shape, str(files["preview.svg"]), opt=SVG_OPTIONS)
    files["preview.svg"].write_text(fit_svg(files["preview.svg"].read_text(encoding="utf-8")), encoding="utf-8")
    meta = measure(shape)
    (workdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return {
        "stl": files["model.stl"].absolute(),
        "step": files["model.step"].absolute(),
        "preview": files["preview.svg"].absolute(),
        "meta": meta,
    }
