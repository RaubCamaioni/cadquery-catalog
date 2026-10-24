"""The app can be served under a URL prefix (ROOT_PATH, uvicorn root_path): every link, asset,
htmx call, redirect and result file link it emits carries that prefix."""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.app import app
from app.routes import tools as tools_routes
from sandboxcore.host import Outcome, Sandbox
from sandboxcore.host.podman import RunResult

from tests.test_auth_routes import FakeGitHub, github  # noqa: F401  (fixture)
from tests.test_tool_routes import StubRunner, public_tool  # noqa: F401  (fixture)

PREFIX = "/models"


def prefixed_client(monkeypatch, runner=None):
    monkeypatch.setattr(tools_routes, "sandbox", Sandbox(tools_routes.ENVIRONMENT.sandbox, runner=runner or StubRunner()))
    return TestClient(app, root_path=PREFIX)


def unprefixed_urls(page: str) -> list[str]:
    """Site-relative URLs in the page that do not start with the prefix."""
    urls = re.findall(r'(?:href|src|hx-get|hx-post|hx-delete|action)="(/[^"]*)"', page)
    return [u for u in urls if not u.startswith(PREFIX + "/") and u != PREFIX]


def test_home_page_assets_and_links_carry_the_prefix(monkeypatch, public_tool):
    page = prefixed_client(monkeypatch).get(PREFIX + "/").text
    assert unprefixed_urls(page) == []
    assert f'href="{PREFIX}/static/output.css' in page and f'src="{PREFIX}/scripts/htmx.min.js"' in page
    assert f'hx-post="{PREFIX}/models' in page  # the listing loader
    # the home link is marked active even though the request path is /models/
    assert re.search(r'href="/models/" class="[^"]*bg-paper', page)


def test_tool_page_and_result_links_carry_the_prefix(monkeypatch, public_tool):
    runner = StubRunner()
    c = prefixed_client(monkeypatch, runner)
    page = c.get(PREFIX + "/model/8").text
    assert unprefixed_urls(page) == []
    assert f'new EventSource("{PREFIX}/trace/"' in page and f"""a[href^="{PREFIX}/download/"]""" in page
    result = c.post(PREFIX + "/model/8", headers={"HX-Request": "true"}).text
    run = PREFIX + "/download/" + runner.calls[-1][1].name
    assert f'<stl-viewer url="{run}/model.stl">' in result
    assert f'href="{run}/model.step"' in result


def test_login_round_trip_stays_under_the_prefix(monkeypatch, github, public_tool):  # noqa: F811
    import html
    from urllib.parse import parse_qs

    c = prefixed_client(monkeypatch)
    page = c.get(PREFIX + "/").text
    state = parse_qs(html.unescape(page.split("https://github.com/login/oauth/authorize?")[1].split('"')[0]))["state"][0]
    r = c.get(PREFIX + "/auth/github", params={"code": "abc", "state": state}, follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == PREFIX + "/"
    page = c.get(PREFIX + "/").text
    assert f'hx-post="{PREFIX}/logout/button"' in page and unprefixed_urls(page) == []


def test_listing_pages_and_their_loader_carry_the_prefix(monkeypatch, public_tool):
    # the second page is requested by a loader rendered inside the first page's response
    monkeypatch.setattr(tools_routes.db_tools, "search_models", lambda *a, **k: [(n, f"t{n}") for n in range(50)])
    page = prefixed_client(monkeypatch).post(PREFIX + "/models?start=0&end=50").text
    assert unprefixed_urls(page) == [] and f'hx-post="{PREFIX}/models?start=50&end=100"' in page


def test_without_a_prefix_nothing_changes(monkeypatch, public_tool):
    monkeypatch.setattr(tools_routes, "sandbox", Sandbox(tools_routes.ENVIRONMENT.sandbox, runner=StubRunner()))
    page = TestClient(app).get("/").text
    assert 'href="/static/output.css' in page and 'hx-post="/models' in page
