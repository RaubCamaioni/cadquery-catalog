"""Every sample model passes the upload checks (entrypoint, annotations, formatting) unchanged."""

from pathlib import Path

import pytest

from app.models import tools as db
from tests.test_tool_routes import create_tool

MODELS = sorted((Path(__file__).resolve().parents[2] / "models").glob("*.py"))


@pytest.mark.parametrize("path", MODELS, ids=[p.stem for p in MODELS])
def test_sample_model_is_accepted_at_upload(path):
    tool = create_tool(1, path.stem, path.read_text(encoding="utf-8"))
    assert tool is not None and tool.name == path.stem
