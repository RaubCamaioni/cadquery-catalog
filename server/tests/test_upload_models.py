"""Uploading a model builds it once with its defaults in the sandbox; what that build produced
(thumbnail, measurements, default STL and STEP) is what the gallery and the model page show."""

from pathlib import Path
from urllib.parse import parse_qs
import html

import pytest
from fastapi.testclient import TestClient

from app import ENVIRONMENT
from app.app import app
from app.models import tools as db
from app.routes import tools as tools_routes
from app.utility.podman_runner import Outcome, RunResult

from tests.test_auth_routes import github  # noqa: F401  (fixture)
from tests.test_tool_routes import StubRunner, built

MODEL = "# box\n\nimport cadquery as cq\n\n\ndef demo_box(size: float = 10) -> cq.Workplane:\n    return cq.Workplane().box(size, size, size)\n"


class BuildingRunner(StubRunner):
    """Writes the files a real sandbox run would leave in the run directory."""

    async def run(self, tool, run_dir, on_line=None):
        result = await super().run(tool, run_dir, on_line)
        if result.outcome is Outcome.OK and isinstance(result.results, dict):
            files = {}
            for key, name in (("stl", "model.stl"), ("step", "model.step"), ("preview", "preview.svg")):
                path = Path(run_dir) / name
                path.write_text(f"<{name}>" if key != "preview" else "<svg>preview</svg>")
                files[key] = path
            result = RunResult(Outcome.OK, results={**result.results, **files})
        return result


@pytest.fixture
def logged_in(monkeypatch, github, tmp_path):  # noqa: F811
    monkeypatch.setattr(tools_routes, "ENVIRONMENT", _env(tools_routes.ENVIRONMENT, tmp_path))
    from app.routes import upload as upload_routes

    monkeypatch.setattr(upload_routes, "ENVIRONMENT", _env(upload_routes.ENVIRONMENT, tmp_path))
    c = TestClient(app)
    page = c.get("/").text
    state = parse_qs(html.unescape(page.split("https://github.com/login/oauth/authorize?")[1].split('"')[0]))["state"][0]
    assert c.get("/auth/github", params={"code": "abc", "state": state}, follow_redirects=False).status_code in (302, 307)
    return c


def _env(env, tmp_path):
    import dataclasses

    return dataclasses.replace(
        env,
        MODELS_DIR=tmp_path / "models",
        sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path / "runs"),
    )


def upload(c, monkeypatch, runner, code=MODEL, name="demo_box.py"):
    monkeypatch.setattr(tools_routes, "runner", runner)
    return c.post("/manage/model/upload", files={"file": (name, code.encode(), "text/x-python")})


def test_upload_validates_and_keeps_the_default_build(monkeypatch, logged_in, tmp_path):
    r = upload(logged_in, monkeypatch, BuildingRunner(built(size_mm=[10, 10, 10])))
    assert r.status_code == 200, r.text
    with db.Session(db.engine) as session:
        model = session.exec(db.select(db.Tool).where(db.Tool.name == "demo_box")).first()
        assert model is not None and model.meta["size_mm"] == [10, 10, 10] and model.preview_svg == "<svg>preview</svg>"
        model_id = model.id
    assert (tmp_path / "models" / str(model_id) / "model.stl").read_text() == "<model.stl>"
    assert (tmp_path / "models" / str(model_id) / "model.step").read_text() == "<model.step>"
    # the thumbnail and the default files are served from what the validation run produced
    preview = logged_in.get(f"/model/{model_id}/preview.svg")
    assert preview.headers["content-type"].startswith("image/svg+xml") and preview.headers["cache-control"] == "no-cache"
    # a browser revalidates with the ETag and gets a 304 while the thumbnail is unchanged
    assert logged_in.get(f"/model/{model_id}/preview.svg", headers={"If-None-Match": preview.headers["etag"]}).status_code == 304
    r = logged_in.get(f"/model/{model_id}/model.stl")
    assert r.status_code == 200 and r.text == "<model.stl>"
    page = logged_in.get(f"/model/{model_id}").text
    assert f'<stl-viewer url="/model/{model_id}/model.stl">' in page and "10 &times; 10 &times; 10 mm" in page


def test_upload_that_fails_to_build_is_rejected_and_not_stored(monkeypatch, logged_in):
    failing = StubRunner(RunResult(Outcome.OK, results="Export Error: NotAModel: a model must return a cadquery Workplane"))
    r = upload(logged_in, monkeypatch, failing, code=MODEL.replace("demo_box", "bad_box"), name="bad_box.py")
    assert r.status_code == 400 and "Model Build Failed: Export Error" in r.json()["detail"]
    with db.Session(db.engine) as session:
        assert session.exec(db.select(db.Tool).where(db.Tool.name == "bad_box")).first() is None


def test_upload_with_a_path_parameter_is_rejected_before_any_build(monkeypatch, logged_in):
    runner = BuildingRunner()
    code = "# tag\n\nfrom pathlib import Path\n\n\ndef with_file(f: Path) -> int:\n    return 1\n"
    r = upload(logged_in, monkeypatch, runner, code=code, name="with_file.py")
    assert r.status_code == 400 and "is a Path" in r.json()["detail"] and runner.calls == []
