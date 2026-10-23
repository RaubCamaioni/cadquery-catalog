"""The host reads a build's files from fixed names in the run directory and never from paths
the run itself reported: model code can write its own result.json."""

import io
import os
from pathlib import Path

import pytest
from sqlmodel import Session
from starlette.datastructures import UploadFile as StarUploadFile

from app.models import tools as db
from app.routes import tools as tools_routes
from app.routes import upload as upload_routes
from app.utility import build_files
from app.utility.build_files import BuildFileError, checked_build
from app.utility.podman_runner import Outcome, RunResult

from tests.test_tool_routes import BUILD, built
from tests.test_auth_routes import github  # noqa: F401  (fixture)
from tests.test_upload_models import BuildingRunner, MODEL, logged_in, upload  # noqa: F401  (fixture)

META = BUILD["meta"]


def run_dir_with_files(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    for name in ("model.stl", "model.step", "preview.svg"):
        (run_dir / name).write_text(f"<{name}>")
    return run_dir


def test_paths_in_the_result_are_ignored(tmp_path):
    run_dir = run_dir_with_files(tmp_path)
    hostile = {"stl": "/proc/self/environ", "step": "/etc/passwd", "preview": "/data/database.db", "meta": META}
    build = checked_build(run_dir, hostile)
    assert build["stl"] == run_dir / "model.stl" and build["preview"] == run_dir / "preview.svg"
    assert build["meta"] == META


@pytest.mark.parametrize("name", ["model.stl", "model.step", "preview.svg"])
def test_a_symlinked_build_file_is_refused(tmp_path, name):
    run_dir = run_dir_with_files(tmp_path)
    secret = tmp_path / "secret"
    secret.write_text("SESSION_KEY=hunter2")
    (run_dir / name).unlink()
    (run_dir / name).symlink_to(secret)
    with pytest.raises(BuildFileError):
        checked_build(run_dir, {**BUILD, "meta": META})


def test_a_missing_file_a_directory_or_a_fifo_is_refused_without_blocking(tmp_path):
    run_dir = run_dir_with_files(tmp_path)
    (run_dir / "model.stl").unlink()
    with pytest.raises(BuildFileError):
        checked_build(run_dir, BUILD)
    (run_dir / "model.stl").mkdir()
    with pytest.raises(BuildFileError):
        checked_build(run_dir, BUILD)
    (run_dir / "model.stl").rmdir()
    os.mkfifo(run_dir / "model.stl")  # opening a FIFO for reading would block until a writer appears
    with pytest.raises(BuildFileError):
        checked_build(run_dir, BUILD)


def test_an_oversized_file_is_refused(tmp_path, monkeypatch):
    run_dir = run_dir_with_files(tmp_path)
    monkeypatch.setitem(build_files.MAX_BYTES, "preview", 8)
    (run_dir / "preview.svg").write_text("<svg>" + "x" * 100 + "</svg>")
    with pytest.raises(BuildFileError):
        checked_build(run_dir, BUILD)


@pytest.mark.parametrize(
    "meta",
    [
        None,
        "<script>",
        {**META, "size_mm": ["<script>alert(1)</script>", 1, 1]},
        {**META, "size_mm": [1, 2]},
        {**META, "volume_mm3": float("nan")},
        {**META, "area_mm2": True},
        {**META, "solids": 1.5},
        {**META, "solids": -1},
        {**META, "extra": "<b>"},
        {k: v for k, v in META.items() if k != "solids"},
    ],
)
def test_measurements_must_be_plain_numbers(tmp_path, meta):
    with pytest.raises(BuildFileError):
        checked_build(run_dir_with_files(tmp_path), {**BUILD, "meta": meta})


class HostileRunner(BuildingRunner):
    """A run whose result.json points at a host file instead of what it built."""

    def __init__(self, secret, **kwargs):
        super().__init__(built(), **kwargs)
        self.secret = secret

    async def run(self, tool, run_dir, on_line=None):
        result = await super().run(tool, run_dir, on_line)
        return RunResult(Outcome.OK, results={**result.results, "stl": self.secret, "preview": self.secret})


def test_an_upload_stores_what_the_run_built_not_a_named_host_file(monkeypatch, logged_in, tmp_path):  # noqa: F811
    secret = tmp_path / "secret.txt"
    secret.write_text("SESSION_KEY=hunter2")
    r = upload(logged_in, monkeypatch, HostileRunner(secret), code=MODEL.replace("demo_box", "hostile_box"), name="hostile_box.py")
    assert r.status_code == 200, r.text
    with Session(db.engine) as session:
        model = session.exec(db.select(db.Tool).where(db.Tool.name == "hostile_box")).first()
        assert model.preview_svg == "<svg>preview</svg>"
        stored = (tmp_path / "models" / str(model.id) / "model.stl").read_text()
    assert stored == "<model.stl>" and "hunter2" not in stored


class SymlinkRunner(BuildingRunner):
    def __init__(self, secret):
        super().__init__(built())
        self.secret = secret

    async def run(self, tool, run_dir, on_line=None):
        result = await super().run(tool, run_dir, on_line)
        (Path(run_dir) / "model.stl").unlink()
        (Path(run_dir) / "model.stl").symlink_to(self.secret)
        return result


def test_an_upload_whose_stl_is_a_symlink_is_rejected(monkeypatch, logged_in, tmp_path):  # noqa: F811
    secret = tmp_path / "secret.txt"
    secret.write_text("SESSION_KEY=hunter2")
    r = upload(logged_in, monkeypatch, SymlinkRunner(secret), code=MODEL.replace("demo_box", "linked_box"), name="linked_box.py")
    assert r.status_code == 400 and "model.stl" in r.text
    with Session(db.engine) as session:
        assert session.exec(db.select(db.Tool).where(db.Tool.name == "linked_box")).first() is None


def test_run_urls_point_into_this_run_whatever_the_result_says(monkeypatch, tmp_path):
    import dataclasses
    from fastapi.testclient import TestClient
    from app.app import app

    env = tools_routes.ENVIRONMENT
    monkeypatch.setattr(tools_routes, "ENVIRONMENT", dataclasses.replace(env, sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path / "runs")))
    tool = db.Tool(id=8, name="box", code=MODEL, arguments={}, public=True, tags=[])
    monkeypatch.setattr(db, "get_tool_by_id", lambda session, id: tool)
    runner = HostileRunner(Path("/runs/someone-else/model.stl"))
    monkeypatch.setattr(tools_routes, "runner", runner)
    r = TestClient(app).post("/model/8")
    assert r.status_code == 200, r.text
    run_dir = runner.calls[0][1]
    assert r.json()["stl"] == "/download" + str(Path(run_dir) / "model.stl")


@pytest.mark.parametrize(
    "filename,expected",
    [("result.json", "result.json"), ("..", "data"), ("../../x.step", "x.step"), ("/etc/cron.d/x", "x"), (".hidden", "hidden")],
)
def test_an_uploaded_parameter_file_gets_its_own_directory(tmp_path, filename, expected):
    tool = db.Tool(id=1, name="m", code="", arguments={"data": ("Path", None)}, tags=[])
    upload_file = StarUploadFile(file=io.BytesIO(b"payload"), filename=filename)
    target = tools_routes._coerce(tool, {"data": upload_file}, tmp_path)["data"]
    assert target.resolve().parent == (tmp_path / "inputs" / "data").resolve() and target.name == expected
    assert target.read_bytes() == b"payload" and not (tmp_path / "result.json").exists()


def test_a_banned_user_cannot_upload_even_with_a_stale_cookie(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.app import app

    with Session(db.engine) as session:
        session.merge(db.User(id=703, alias="gone", banned=True))
        session.commit()
    monkeypatch.setattr(upload_routes, "session_user", lambda request: db.User(id=703, alias="gone"))
    monkeypatch.setattr(tools_routes, "runner", BuildingRunner(built()))
    r = TestClient(app).post("/manage/model/upload", files={"file": ("banned_box.py", MODEL.encode())})
    assert r.status_code == 403
