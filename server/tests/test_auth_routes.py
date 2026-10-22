import html
import json
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.routes import auth as auth_routes
from app.models import tools as db


class FakeGitHub:
    """Stands in for GitHub's OAuth endpoints."""

    def __init__(self, user=None, fail=False):
        self.user, self.fail, self.codes = user or {"id": 12345, "login": "octocat"}, fail, []
        self.configured = True

    def login_url(self, state):
        return f"https://github.com/login/oauth/authorize?client_id=test&state={state}"

    async def user_for_code(self, code):
        self.codes.append(code)
        if self.fail:
            raise auth_routes.GitHubLoginError("bad code")
        return self.user


def login_href(c):
    """The login link's URL as a browser sees it (Jinja escapes & as &amp; in attributes)."""
    return html.unescape(c.get("/login/button").text.split('href="')[1].split('"')[0])


def state_for(c):
    return parse_qs(urlparse(login_href(c)).query)["state"][0]


@pytest.fixture
def github(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(auth_routes, "github", fake)
    monkeypatch.setattr(auth_routes, "OWNER_GITHUB_LOGIN", "RaubCamaioni")
    # the route imported get_user by name, so patch it where it is used
    monkeypatch.setattr(auth_routes, "get_user", lambda session, id: db.User(id=id))
    return fake


def test_login_button_links_to_github_with_state(github):
    c = TestClient(app)
    url = login_href(c)
    assert url.startswith("https://github.com/login/oauth/authorize")
    assert len(parse_qs(urlparse(url).query)["state"][0]) >= 16


def test_callback_accepts_a_recent_state_after_the_button_was_rendered_again(github):
    # a second tab or a reloaded header renders the button again; the first tab's login must still work
    c = TestClient(app)
    first = state_for(c)
    state_for(c)
    r = c.get("/auth/github", params={"code": "abc", "state": first}, follow_redirects=False)
    assert r.status_code in (302, 307)


def test_header_renders_the_login_state_without_a_second_request(github):
    # the control is part of the page itself (no htmx fetch after load, so no [login] -> [logout] flicker)
    c = TestClient(app)
    page = c.get("/").text
    assert "[login]" in page and "[logout]" not in page and "/login/button" not in page
    query = html.unescape(page.split("https://github.com/login/oauth/authorize?")[1].split('"')[0])
    state = parse_qs(query)["state"][0]
    # the state issued while rendering the page was saved in that page's session cookie
    r = c.get("/auth/github", params={"code": "abc", "state": state}, follow_redirects=False)
    assert r.status_code in (302, 307)
    page = c.get("/").text
    assert "[logout]" in page and "[login]" not in page


def test_callback_rejects_wrong_state(github):
    c = TestClient(app)
    c.get("/login/button")  # creates the session state
    r = c.get("/auth/github", params={"code": "abc", "state": "not-the-state"}, follow_redirects=False)
    assert r.status_code == 403 and github.codes == []


def test_callback_logs_in_and_redirects_home(github):
    c = TestClient(app)
    state = state_for(c)
    r = c.get("/auth/github", params={"code": "abc", "state": state}, follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/"
    assert github.codes == ["abc"]
    assert "[logout]" in c.get("/login/button").text
    assert "octocat@catalog" in c.get("/").text  # the prompt shows the alias (defaults to the GitHub login)


def test_header_highlights_the_current_page(github):
    import re

    def active(html):
        # the one nav link rendered with the inverted (active) classes
        return re.findall(r'class="[^"]*bg-paper text-ink[^"]*">\[(\w+)\]', html)

    c = TestClient(app)
    assert active(c.get("/").text) == ["home"]
    assert active(c.get("/privacy-policy").text) == ["privacy"]
    assert active(c.get("/terms-of-service").text) == ["terms"]
    assert active(c.get("/user").text) == ["profile"]


def test_header_prompt_shows_user_and_directory(github):
    c = TestClient(app)
    assert "anonymous@catalog</span>:~<" in c.get("/").text
    assert "anonymous@catalog</span>:~/catalog<" in c.get("/user").text
    assert "anonymous@catalog</span>:~/privacy<" in c.get("/privacy-policy").text
    assert "anonymous@catalog</span>:~/terms<" in c.get("/terms-of-service").text


def test_owner_github_login_maps_to_existing_user_id(github):
    github.user = {"id": 999, "login": "RaubCamaioni"}
    c = TestClient(app)
    state = state_for(c)
    c.get("/auth/github", params={"code": "abc", "state": state}, follow_redirects=False)
    assert json.loads(c.cookies and c.get("/whoami").text)["id"] == 49600918


def test_other_users_get_an_id_derived_from_their_github_id(github):
    c = TestClient(app)
    state = state_for(c)
    c.get("/auth/github", params={"code": "abc", "state": state}, follow_redirects=False)
    me = json.loads(c.get("/whoami").text)
    assert me["id"] == db.hash_id("github:12345") and me["alias"] == "octocat"


def test_github_failure_is_403(github):
    github.fail = True
    c = TestClient(app)
    state = state_for(c)
    assert c.get("/auth/github", params={"code": "abc", "state": state}, follow_redirects=False).status_code == 403


async def test_user_for_code_reports_githubs_error_text():
    # GitHub answers a bad exchange with HTTP 200 and an error field; the reason must reach the log
    import httpx

    def handler(request):
        return httpx.Response(200, json={"error": "incorrect_client_credentials", "error_description": "The client_id and/or client_secret passed are incorrect."})

    oauth = auth_routes.GitHubOAuth("id", "secret", "https://pywebtools.com/auth/github")
    oauth.transport = httpx.MockTransport(handler)
    with pytest.raises(auth_routes.GitHubLoginError) as e:
        await oauth.user_for_code("code")
    assert "incorrect_client_credentials" in str(e.value)


def test_login_button_says_unavailable_without_github_keys(github):
    github.configured = False
    page = TestClient(app).get("/login/button").text
    assert "login unavailable" in page and "github.com" not in page


def test_privacy_policy_states_what_the_github_login_collects():
    page = TestClient(app).get("/privacy-policy").text
    assert '"read:user"' in page and "account id" in page and "username" in page
    assert "no email address" in page and "discarded" in page  # nothing else is read; the token is not kept
