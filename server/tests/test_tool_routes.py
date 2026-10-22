import asyncio
import dataclasses
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.models import tools as db
from app.routes import tools as tools_routes
from app.utility.podman_runner import Outcome, RunResult, SandboxBusy, SandboxUnavailable


# what the sandbox returns for a model that built: the export dict (see sandbox/export.py)
BUILD = {
    "stl": Path("/runs/a/model.stl"),
    "step": Path("/runs/a/model.step"),
    "preview": Path("/runs/a/preview.svg"),
    "meta": {"size_mm": [30, 20, 10], "volume_mm3": 6000.0, "area_mm2": 2200.0, "solids": 1},
}


def built(**meta):
    return RunResult(Outcome.OK, results={**BUILD, "meta": {**BUILD["meta"], **meta}})


class StubRunner:
    def __init__(self, result=None, raise_=None, available=True):
        self.result = result if result is not None else built()
        self.raise_, self.available = raise_, available
        self.unavailable_reason = None if available else "self-test failed"
        self.calls = []
        self.on_line = None

    async def start(self):
        pass

    def start_in_background(self):
        asyncio.create_task(self.start())

    async def stop(self):
        pass

    async def run(self, tool, run_dir, on_line=None):
        self.calls.append((tool, run_dir))
        self.on_line = on_line
        if self.raise_:
            raise self.raise_
        return self.result


@pytest.fixture
def public_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(
        db,
        "get_tool_by_id",
        lambda session, id: db.Tool(
            id=8, name="byte_converter", code="def byte_converter(): return 1", arguments={}, public=True, tags=[]
        ),
    )
    # SandboxConfig is frozen: swap the whole ENVIRONMENT the routes module sees
    env = tools_routes.ENVIRONMENT
    monkeypatch.setattr(
        tools_routes,
        "ENVIRONMENT",
        dataclasses.replace(env, sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path)),
    )


def client(monkeypatch, runner):
    monkeypatch.setattr(tools_routes, "runner", runner)
    return TestClient(app)


def test_code_view_shows_the_trailing_newline_as_an_empty_last_line(monkeypatch, public_tool):
    code = "# tag\n\n\ndef byte_converter() -> int:\n    return 1\n"
    monkeypatch.setattr(db, "get_tool_by_id", lambda session, id: db.Tool(id=8, name="t", code=code, public=True, tags=[]))
    page = client(monkeypatch, StubRunner()).get("/model/8").text
    # the view's text ends in two newlines, so Prism numbers an empty line 6; the status bar counts 5 like vim
    assert "    return 1\n\n</code>" in page and ">5L<" in page


def test_code_view_without_a_trailing_newline_adds_none(monkeypatch, public_tool):
    page = client(monkeypatch, StubRunner()).get("/model/8").text  # the fixture's code has no newline at all
    assert "return 1</code>" in page and ">1L<" in page


def test_run_tool_ok_renders_results(monkeypatch, public_tool):
    c = client(monkeypatch, StubRunner(built()))
    r = c.post("/model/8")
    assert r.status_code == 200
    body = json.loads(r.text)
    assert body["stl"] == "/download/runs/a/model.stl" and body["step"] == "/download/runs/a/model.step"
    assert body["meta"]["size_mm"] == [30, 20, 10]
    # the page gets the viewer, the measurements and the download links
    page = c.post("/model/8", headers={"HX-Request": "true"}).text
    assert '<stl-viewer url="/download/runs/a/model.stl">' in page
    assert "30 &times; 20 &times; 10 mm" in page and "6.00 cm&sup3;" in page
    assert 'href="/download/runs/a/model.step" download="byte_converter.step"' in page


def test_run_that_returns_no_model_is_a_failure(monkeypatch, public_tool):
    # the runtime writes its own error text as the result when the entrypoint did not return a model
    c = client(monkeypatch, StubRunner(RunResult(Outcome.OK, results="Export Error: NotAModel: a model must return ...")))
    r = c.post("/model/8")
    assert r.status_code == 422 and r.json()["detail"].startswith("Export Error")
    page = c.post("/model/8", headers={"HX-Request": "true"}).text
    assert "Export Error" in page and "<stl-viewer" not in page


def test_run_tool_timeout_message_htmx(monkeypatch, public_tool):
    c = client(monkeypatch, StubRunner(RunResult(Outcome.TIMEOUT, message="Tool exceeded the 10 second limit")))
    r = c.post("/model/8", headers={"HX-Request": "true"})
    assert r.status_code == 200 and "Tool exceeded the 10 second limit" in r.text


def test_run_tool_malformed_result_renders_failure(monkeypatch, public_tool):
    c = client(monkeypatch, StubRunner(RunResult(Outcome.CRASHED, message="Tool failed to run", stderr_tail="boom")))
    r = c.post("/model/8")
    assert r.status_code == 422 and r.json() == {"detail": "Tool failed to run\nboom"}


def test_run_tool_busy_is_503(monkeypatch, public_tool):
    r = client(monkeypatch, StubRunner(raise_=SandboxBusy())).post("/model/8")
    assert r.status_code == 503 and r.json()["detail"] == "Server busy, try again"


def test_run_tool_unavailable_returns_503_without_slot(monkeypatch, public_tool):
    stub = StubRunner(raise_=SandboxUnavailable(), available=False)
    r = client(monkeypatch, stub).post("/model/8")
    assert r.status_code == 503 and r.json()["detail"] == "Sandbox unavailable"
    assert stub.calls == []  # route checks runner.available before writing files or running


def test_lifespan_does_not_wait_for_runner_start(monkeypatch):
    import time

    class SlowStartRunner(StubRunner):
        async def start(self):
            await asyncio.sleep(3)

    monkeypatch.setattr(tools_routes, "runner", SlowStartRunner(available=False))
    started = time.monotonic()
    with TestClient(app) as c:
        assert c.get("/healthz").status_code == 503
    assert time.monotonic() - started < 2  # pages are served while the sandbox is still starting


def test_stylesheet_urls_are_versioned(monkeypatch, public_tool):
    import re

    c = client(monkeypatch, StubRunner())
    for path in ("/", "/model/8"):
        html = c.get(path).text
        # same URL + new content gets served from browser caches; the version query defeats that
        assert re.search(r'/static/output\.css\?v=[0-9a-f]{8,}"', html), path
    assert re.search(r'/static/prism-vim\.css\?v=[0-9a-f]{8,}"', c.get("/model/8").text)


def test_healthz(monkeypatch):
    assert client(monkeypatch, StubRunner()).get("/healthz").json() == {"sandbox": "ready"}
    r = client(monkeypatch, StubRunner(available=False)).get("/healthz")
    assert r.status_code == 503 and r.json() == {"sandbox": "unavailable", "reason": "self-test failed"}


def test_run_dir_created_under_configured_root(monkeypatch, public_tool, tmp_path):
    stub = StubRunner(RunResult(Outcome.OK, results=None))
    client(monkeypatch, stub).post("/model/8")
    tool, run_dir = stub.calls[0]
    assert run_dir.parent == tmp_path and tool == run_dir / "byte_converter.py"


def test_tool_page_names_the_author_as_alias_and_id(monkeypatch, tmp_path):
    import dataclasses

    monkeypatch.setattr(
        db,
        "get_tool_by_id",
        lambda session, id: db.Tool(id=8, name="t", code="", arguments={}, public=True, annonymous=False, user_id=49600918, tags=[]),
    )
    monkeypatch.setattr(tools_routes.db_tools, "get_user_by_id", lambda session, id: db.User(id=49600918, alias="rob"))
    env = tools_routes.ENVIRONMENT
    monkeypatch.setattr(tools_routes, "ENVIRONMENT", dataclasses.replace(env, sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path)))
    page = client(monkeypatch, StubRunner()).get("/model/8").text
    assert "rob#49600918" in page
    assert page.index("t.py</span>") < page.index("rob#49600918") < page.index('id="vim-mode"')  # status bar, after the name
    assert "vim t.py" not in page  # no heading above the code


def test_anonymous_tool_hides_the_alias_and_the_id(monkeypatch, tmp_path):
    import dataclasses

    monkeypatch.setattr(
        db,
        "get_tool_by_id",
        lambda session, id: db.Tool(id=8, name="t", code="", arguments={}, public=True, annonymous=True, user_id=49600918, tags=[]),
    )
    monkeypatch.setattr(tools_routes.db_tools, "get_user_by_id", lambda session, id: db.User(id=49600918, alias="rob"))
    env = tools_routes.ENVIRONMENT
    monkeypatch.setattr(tools_routes, "ENVIRONMENT", dataclasses.replace(env, sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path)))
    page = client(monkeypatch, StubRunner()).get("/model/8").text
    assert "anonymous#00000000" in page and "rob#" not in page and "49600918" not in page


def test_every_page_carries_the_version_tag(monkeypatch, public_tool):
    from app import TEMPLATES

    version, sha = TEMPLATES.env.globals["app_version"], TEMPLATES.env.globals["commit_sha"]
    c = client(monkeypatch, StubRunner())
    for path in ("/", "/model/8", "/privacy-policy"):
        page = c.get(path).text
        assert 'id="version-tag"' in page and f">v{version}+{sha[:7]}<" in page, path
        assert f"github.com/RaubCamaioni/cadquery-catalog/commit/{sha}" in page


def download_url(path):
    return "/download/" + str(path.resolve().relative_to(path.resolve().anchor)).replace("\\", "/")


def test_download_serves_a_file_from_a_run_directory(monkeypatch, public_tool, tmp_path):
    run = tmp_path / "abc"
    run.mkdir()
    (run / "qr_code.png").write_bytes(b"png")
    r = client(monkeypatch, StubRunner()).get(download_url(run / "qr_code.png"))
    assert r.status_code == 200 and r.content == b"png"
    assert "qr_code.png" in r.headers["content-disposition"]


def test_image_preview_is_served_inline_with_its_media_type(monkeypatch, public_tool, tmp_path):
    run = tmp_path / "abc"
    run.mkdir()
    (run / "qr_code.png").write_bytes(b"png")
    (run / "data.csv").write_bytes(b"a,b")
    (run / "song.mp3").write_bytes(b"mp3")
    (run / "doc.pdf").write_bytes(b"pdf")
    c = client(monkeypatch, StubRunner())
    for name, media_type in (("qr_code.png", "image/png"), ("song.mp3", "audio/mpeg"), ("doc.pdf", "application/pdf")):
        r = c.get(download_url(run / name) + "?preview=1")
        assert r.status_code == 200 and r.headers["content-type"] == media_type, name
        assert r.headers["content-disposition"].startswith("inline")
    # preview only changes how images are served; anything else stays a download
    r = c.get(download_url(run / "data.csv") + "?preview=1")
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["content-disposition"].startswith("attachment")


def test_download_of_an_expired_result_is_404_with_a_reason(monkeypatch, public_tool, tmp_path):
    r = client(monkeypatch, StubRunner()).get(download_url(tmp_path / "gone" / "qr_code.png"))
    assert r.status_code == 404 and "expired" in r.json()["detail"]


def test_download_outside_the_run_root_is_forbidden(monkeypatch, public_tool, tmp_path):
    outside = tmp_path.parent / "elsewhere.txt"
    outside.write_text("x")
    assert client(monkeypatch, StubRunner()).get(download_url(outside)).status_code == 403
    assert client(monkeypatch, StubRunner()).get(download_url(tmp_path)).status_code == 403  # the root itself


def test_tool_page_downloads_results_in_place(monkeypatch, public_tool):
    page = client(monkeypatch, StubRunner()).get("/model/8").text
    assert """closest('a[href^="/download/"]')""" in page and "event.preventDefault()" in page
