"""A build's files. Model code writes its own result.json, so nothing it names is trusted: sandboxcore
vets every returned path (a regular file inside the run, reached without symlinks) or refuses the run,
and the catalog takes each export only under its fixed name, within its size cap, and the measurements
only in their numeric shape."""

import dataclasses
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.app import app
from app.models import tools as db
from app.routes import tools as tools_routes
from app.routes import upload as upload_routes
from app.utility import build_files
from app.utility.build_files import BuildFileError, checked_build
from sandboxcore.host import Outcome, OutputFile, Sandbox
from sandboxcore.host.podman import RunResult

from tests.test_tool_routes import BUILD, StubRunner, built
from tests.test_auth_routes import github  # noqa: F401  (fixture)
from tests.test_upload_models import BuildingRunner, MODEL, logged_in, upload  # noqa: F401  (fixture)

META = BUILD["meta"]
NAMES = {"stl": "model.stl", "step": "model.step", "preview": "preview.svg"}
NOT_MADE = "Tool returned a path that is not a file it made"


def outputs(tmp_path, **override):
    """An export dict as Sandbox.run returns it: OutputFiles of real files in a run directory."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    result = {"meta": META}
    for key, name in NAMES.items():
        path = run_dir / name
        if not path.exists():
            path.write_text(f"<{name}>")
        result[key] = OutputFile("r" * 32, name, path.stat().st_size, path)
    result.update(override)
    return result


def test_a_vetted_build_passes(tmp_path):
    build = checked_build(outputs(tmp_path))
    assert build["stl"].name == "model.stl" and build["preview"].name == "preview.svg" and build["meta"] == META


@pytest.mark.parametrize("key", list(NAMES))
def test_each_export_must_have_its_fixed_name(tmp_path, key):
    other = outputs(tmp_path)["stl" if key != "stl" else "step"]
    with pytest.raises(BuildFileError):
        checked_build(outputs(tmp_path, **{key: other}))


@pytest.mark.parametrize("value", [None, "/proc/self/environ", Path("/etc/passwd")])
def test_an_export_that_is_not_a_vetted_file_is_refused(tmp_path, value):
    with pytest.raises(BuildFileError):
        checked_build(outputs(tmp_path, stl=value))


def test_an_export_swapped_after_the_run_is_read_without_following_or_blocking(tmp_path):
    build = outputs(tmp_path)
    path = build["stl"].path
    path.unlink()
    os.mkfifo(path)  # opening a FIFO for reading would block until a writer appears
    with pytest.raises(BuildFileError):
        checked_build(build)
    path.unlink()
    (tmp_path / "secret").write_text("SESSION_KEY=hunter2")
    path.symlink_to(tmp_path / "secret")
    with pytest.raises(BuildFileError):
        checked_build(build)


def test_an_oversized_file_is_refused(tmp_path, monkeypatch):
    monkeypatch.setitem(build_files.MAX_BYTES, "preview", 8)
    build = outputs(tmp_path)
    build["preview"].path.write_text("<svg>" + "x" * 100 + "</svg>")
    with pytest.raises(BuildFileError):
        checked_build(build)


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
        checked_build(outputs(tmp_path, meta=meta))


class HostileRunner(BuildingRunner):
    """A run whose result.json points at a host file instead of what it built."""

    def __init__(self, secret, **kwargs):
        super().__init__(built(), **kwargs)
        self.secret = secret

    async def run(self, tool, run_dir, on_line=None, runtime_args=()):
        if runtime_args:  # --inspect: the real runtime, as StubRunner does it
            return await super().run(tool, run_dir, on_line, runtime_args)
        result = await super().run(tool, run_dir, on_line)
        return RunResult(Outcome.OK, results={**result.results, "stl": self.secret, "preview": self.secret})


def stored(name):
    with Session(db.engine) as session:
        return session.exec(db.select(db.Tool).where(db.Tool.name == name)).first()


def test_an_upload_whose_build_names_a_host_file_is_rejected(monkeypatch, logged_in, tmp_path):  # noqa: F811
    secret = tmp_path / "secret.txt"
    secret.write_text("SESSION_KEY=hunter2")
    r = upload(logged_in, monkeypatch, HostileRunner(secret), code=MODEL.replace("demo_box", "hostile_box"), name="hostile_box.py")
    assert r.status_code == 400 and NOT_MADE in r.text and "hunter2" not in r.text
    assert stored("hostile_box") is None


class SymlinkRunner(BuildingRunner):
    def __init__(self, secret):
        super().__init__(built())
        self.secret = secret

    async def run(self, tool, run_dir, on_line=None, runtime_args=()):
        if runtime_args:  # --inspect: the real runtime, as StubRunner does it
            return await super().run(tool, run_dir, on_line, runtime_args)
        result = await super().run(tool, run_dir, on_line)
        (Path(run_dir) / "model.stl").unlink()
        (Path(run_dir) / "model.stl").symlink_to(self.secret)
        return result


def test_an_upload_whose_stl_is_a_symlink_is_rejected(monkeypatch, logged_in, tmp_path):  # noqa: F811
    secret = tmp_path / "secret.txt"
    secret.write_text("SESSION_KEY=hunter2")
    r = upload(logged_in, monkeypatch, SymlinkRunner(secret), code=MODEL.replace("demo_box", "linked_box"), name="linked_box.py")
    assert r.status_code == 400 and NOT_MADE in r.text
    assert stored("linked_box") is None


def model_client(monkeypatch, tmp_path, runner, tool):
    env = tools_routes.ENVIRONMENT
    monkeypatch.setattr(
        tools_routes, "ENVIRONMENT", dataclasses.replace(env, sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path / "runs"))
    )
    monkeypatch.setattr(db, "get_tool_by_id", lambda session, id: tool)
    monkeypatch.setattr(tools_routes, "sandbox", Sandbox(tools_routes.ENVIRONMENT.sandbox, runner=runner))
    return TestClient(app)


def test_a_run_whose_result_names_another_runs_file_is_refused(monkeypatch, tmp_path):
    tool = db.Tool(id=8, name="box", code=MODEL, arguments={}, public=True)
    c = model_client(monkeypatch, tmp_path, HostileRunner(Path("/runs/someone-else/model.stl")), tool)
    r = c.post("/model/8")
    assert r.status_code == 422 and r.json() == {"detail": NOT_MADE}


class ArgsRunner(StubRunner):
    """Keeps what the app staged for the run (the run directory is removed when the request ends)."""

    async def run(self, tool, run_dir, on_line=None, runtime_args=()):
        if not runtime_args:
            self.args = json.loads((Path(run_dir) / "args.json").read_text())
            self.run_dir = Path(run_dir)
        return await super().run(tool, run_dir, on_line, runtime_args)


@pytest.mark.parametrize(
    "filename,expected",
    [("result.json", "result.json"), ("..", "data"), ("../../x.step", "x.step"), ("/etc/cron.d/x", "x"), (".hidden", "hidden")],
)
def test_an_uploaded_parameter_file_gets_its_own_directory(monkeypatch, tmp_path, filename, expected):
    tool = db.Tool(id=8, name="m", code="", arguments={"data": ("Path", "None")}, public=True)
    runner = ArgsRunner()
    r = model_client(monkeypatch, tmp_path, runner, tool).post("/model/8", files={"data": (filename, b"payload")})
    assert r.status_code == 200, r.text
    target = Path(runner.args["data"]["__path__"])
    assert target.parent == runner.run_dir / "inputs" / "data" and target.name == expected


def test_a_banned_user_cannot_upload_even_with_a_stale_cookie(monkeypatch, tmp_path):
    with Session(db.engine) as session:
        session.merge(db.User(id=703, alias="gone", banned=True))
        session.commit()
    monkeypatch.setattr(upload_routes, "session_user", lambda request: db.User(id=703, alias="gone"))
    monkeypatch.setattr(tools_routes, "sandbox", Sandbox(tools_routes.ENVIRONMENT.sandbox, runner=BuildingRunner(built())))
    r = TestClient(app).post("/manage/model/upload", files={"file": ("banned_box.py", MODEL.encode())})
    assert r.status_code == 403
