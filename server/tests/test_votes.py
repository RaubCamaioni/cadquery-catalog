from sqlmodel import Session

from app.models import tools as db
from app.routes import tools as tools_routes

from tests.test_admin import engine_with
from tests.test_tool_routes import StubRunner, client, public_tool  # noqa: F401  (fixture)


def votes_engine():
    return engine_with(
        users=[db.User(id=1, alias="rob"), db.User(id=2, alias="eve")],
        tools=[db.Tool(id=8, name="byte_converter", code="", user_id=1, public=True)],
    )


def test_vote_toggles_and_switches():
    with Session(votes_engine()) as session:
        assert db.set_vote(session, user_id=2, tool_id=8, direction="up") == "up"
        assert db.vote_counts(session, 8) == (1, 0)
        assert db.set_vote(session, user_id=2, tool_id=8, direction="down") == "down"  # switches
        assert db.vote_counts(session, 8) == (0, 1)
        assert db.set_vote(session, user_id=2, tool_id=8, direction="down") is None  # same again: removed
        assert db.vote_counts(session, 8) == (0, 0)
        db.set_vote(session, 1, 8, "up")
        db.set_vote(session, 2, 8, "up")
        assert db.vote_counts(session, 8) == (2, 0) and db.user_vote(session, 2, 8) == "up"


def test_one_report_per_user_with_the_latest_reason():
    with Session(votes_engine()) as session:
        db.add_report(session, user_id=2, tool_id=8, reason="spam")
        db.add_report(session, user_id=2, tool_id=8, reason="malware")
        db.add_report(session, user_id=1, tool_id=8, reason="broken")
        reports = session.exec(db.select(db.Report).where(db.Report.tool_id == 8)).all()
        assert sorted((r.user_id, r.reason) for r in reports) == [(1, "broken"), (2, "malware")]
        assert db.has_reported(session, 2, 8) and not db.has_reported(session, 3, 8)


def test_tool_page_shows_vote_counts_and_report(monkeypatch, public_tool):
    monkeypatch.setattr(tools_routes.db_tools, "vote_counts", lambda session, tool_id: (12, 3))
    page = client(monkeypatch, StubRunner()).get("/model/8").text
    assert "[up 12]" in page and "[down 3]" in page and "[report]" in page


def test_anonymous_vote_asks_for_login(monkeypatch, public_tool):
    r = client(monkeypatch, StubRunner()).post("/model/8/vote", params={"direction": "up"})
    assert r.status_code == 200 and "[login to vote]" in r.text


def test_logged_in_vote_returns_the_updated_fragment(monkeypatch, public_tool):
    calls = []
    monkeypatch.setattr(tools_routes, "session_user", lambda request: db.User(id=2, alias="eve"))
    monkeypatch.setattr(tools_routes.db_tools, "set_vote", lambda session, user_id, tool_id, direction: calls.append((user_id, tool_id, direction)) or "up")
    monkeypatch.setattr(tools_routes.db_tools, "vote_counts", lambda session, tool_id: (13, 3))
    monkeypatch.setattr(tools_routes.db_tools, "user_vote", lambda session, user_id, tool_id: "up")
    monkeypatch.setattr(tools_routes.db_tools, "has_reported", lambda session, user_id, tool_id: False)
    r = client(monkeypatch, StubRunner()).post("/model/8/vote", params={"direction": "up"})
    assert r.status_code == 200 and calls == [(2, 8, "up")]
    assert "[up 13]" in r.text and "switch-on" in r.text  # the user's own vote is inverted
    assert client(monkeypatch, StubRunner()).post("/model/8/vote", params={"direction": "sideways"}).status_code == 400


def test_report_records_the_reason_and_shows_reported(monkeypatch, public_tool):
    calls = []
    monkeypatch.setattr(tools_routes, "session_user", lambda request: db.User(id=2, alias="eve"))
    monkeypatch.setattr(tools_routes.db_tools, "add_report", lambda session, user_id, tool_id, reason: calls.append((user_id, tool_id, reason)))
    monkeypatch.setattr(tools_routes.db_tools, "vote_counts", lambda session, tool_id: (0, 0))
    monkeypatch.setattr(tools_routes.db_tools, "user_vote", lambda session, user_id, tool_id: None)
    monkeypatch.setattr(tools_routes.db_tools, "has_reported", lambda session, user_id, tool_id: True)
    c = client(monkeypatch, StubRunner())
    r = c.post("/model/8/report", data={"reason": "  posts malware  "})
    assert r.status_code == 200 and calls == [(2, 8, "posts malware")] and "[reported]" in r.text
    assert c.post("/model/8/report", data={"reason": "   "}).status_code == 400  # a reason is required
    assert client(monkeypatch, StubRunner()).post("/model/8/report", data={"reason": "x" * 1001}).status_code == 400


def test_anonymous_report_asks_for_login(monkeypatch, public_tool):
    r = client(monkeypatch, StubRunner()).post("/model/8/report", data={"reason": "spam"})
    assert r.status_code == 200 and "[login to report]" in r.text
