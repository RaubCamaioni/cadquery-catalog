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

# white strokes: the site draws thumbnails on a black background
SVG_OPTIONS = {
    "width": 480,
    "height": 360,
    "marginLeft": 24,
    "marginTop": 24,
    "showAxes": False,
    "projectionDir": (1.0, -1.0, 0.8),
    "strokeWidth": 0.6,
    "strokeColor": (255, 255, 255),
    "hiddenColor": (90, 90, 90),
    "showHidden": False,
}


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


def export_model(result: Any, workdir: Path | None = None) -> dict:
    from cadquery import exporters

    workdir = Path(workdir or Path.cwd())
    shape = to_shape(result)
    files = {name: workdir / name for name in ("model.stl", "model.step", "preview.svg")}
    exporters.export(shape, str(files["model.stl"]))
    exporters.export(shape, str(files["model.step"]))
    exporters.export(shape, str(files["preview.svg"]), opt=SVG_OPTIONS)
    meta = measure(shape)
    (workdir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return {
        "stl": files["model.stl"].absolute(),
        "step": files["model.step"].absolute(),
        "preview": files["preview.svg"].absolute(),
        "meta": meta,
    }
