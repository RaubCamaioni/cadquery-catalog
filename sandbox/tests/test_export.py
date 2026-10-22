import json
from pathlib import Path

import pytest

cq = pytest.importorskip("cadquery")

from sandbox.export import NotAModel, export_model, to_shape  # noqa: E402


def box():
    return cq.Workplane("XY").box(30, 20, 10)


def test_export_writes_stl_step_preview_and_meta(tmp_path):
    result = export_model(box(), tmp_path)
    for name in ("model.stl", "model.step", "preview.svg", "meta.json"):
        assert (tmp_path / name).stat().st_size > 0, name
    assert result["stl"] == (tmp_path / "model.stl").absolute() and result["step"].suffix == ".step"
    meta = json.loads((tmp_path / "meta.json").read_text())
    assert meta == result["meta"]
    assert meta["size_mm"] == [30, 20, 10] and meta["volume_mm3"] == pytest.approx(6000) and meta["solids"] == 1
    svg = (tmp_path / "preview.svg").read_text()
    assert svg.startswith("<?xml") or "<svg" in svg
    assert "rgb(255,255,255)" in svg  # white strokes for the black background


def test_shape_and_assembly_are_accepted(tmp_path):
    assert to_shape(box().val()).Volume() == pytest.approx(6000)
    assembly = cq.Assembly().add(box(), name="a").add(box().translate((40, 0, 0)), name="b")
    assert to_shape(assembly).Volume() == pytest.approx(12000)
    # a workplane with several solids becomes one compound
    two = cq.Workplane("XY").pushPoints([(0, 0), (50, 0)]).box(10, 10, 10)
    assert len(to_shape(two).Solids()) == 2


@pytest.mark.parametrize("value", [None, 42, "not a model", Path("model.stl"), cq.Workplane("XY")])
def test_other_return_values_are_rejected(value):
    with pytest.raises(NotAModel):
        to_shape(value)
