"""models/catalog.yaml carries the repo models' metadata: it must match the files and the category tree."""

from pathlib import Path

import pytest
import yaml

from app.metadata.categories import Categories
from app.metadata.tags import Tags

# the repo root locally; in the test container the models folder is copied to /models
REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "models"


@pytest.mark.skipif(not (MODELS / "catalog.yaml").exists(), reason="no models folder beside the server")
def test_manifest_matches_models_and_tree():
    manifest = yaml.safe_load((MODELS / "catalog.yaml").read_text(encoding="utf-8"))
    files = {p.stem for p in MODELS.glob("*.py")}
    assert set(manifest) == files
    for name, entry in manifest.items():
        assert set(entry) == {"tags", "categories"}, name
        tags = Tags().parse({"tags.present": ["1"], "tags": [str(t) for t in entry["tags"]]})
        assert tags == [str(t) for t in entry["tags"]], f"{name}: tags are not in normal form"
        assert Categories().parse({"categories.present": ["1"], "categories": entry["categories"]}), name
        # metadata lives in the manifest now, not on line 1
        assert not (MODELS / f"{name}.py").read_text(encoding="utf-8").startswith("# "), name
