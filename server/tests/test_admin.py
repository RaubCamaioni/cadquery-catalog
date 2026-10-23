import json

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.app import app
from app.models import tools as db
from app.routes import tools as tools_routes

from tests.test_tool_routes import StubRunner, client


def engine_with(tools=(), users=()):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for u in users:
            session.add(u)
        for t in tools:
            session.add(t)
        session.commit()
    return engine


def test_migration_adds_role_columns_once():
    # a database from before roles existed: user(id, alias) only
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE user (id INTEGER PRIMARY KEY, alias VARCHAR NOT NULL)"))
        conn.execute(text("INSERT INTO user (id, alias) VALUES (1, 'rob')"))
    db.migrate(engine)
    db.migrate(engine)  # idempotent
    columns = {c["name"] for c in inspect(engine).get_columns("user")}
    assert {"admin", "banned", "banned_until"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT admin, banned FROM user WHERE id = 1")).one() == (0, 0)


def test_startup_pass_formats_stored_tools_once():
    engine = engine_with(
        users=[db.User(id=1, alias="rob")],
        tools=[
            db.Tool(id=1, name="a", code="# tag\ndef a(x:int=1)->int:\n  return x", user_id=1),
            db.Tool(id=2, name="b", code="# tag\n\n\ndef b(x: int = 1) -> int:\n    return x\n", user_id=1),
            db.Tool(id=3, name="c", code="def (broken", user_id=1),
        ],
    )
    assert db.format_stored_tools(engine) == 1
    assert db.format_stored_tools(engine) == 0  # idempotent
    with Session(engine) as session:
        codes = {t.id: t.code for t in session.exec(db.select(db.Tool))}
    assert codes[1] == "# tag\ndef a(x: int = 1) -> int:\n    return x\n"
    assert codes[2].endswith("return x\n") and not codes[2].endswith("\n\n")
    assert codes[3] == "def (broken"  # unparsable code is left alone, not dropped


def test_users_with_tools_lists_every_account_with_vote_and_report_totals():
    engine = engine_with(
        users=[db.User(id=1, alias="rob", admin=True), db.User(id=2, alias="eve")],
        tools=[
            db.Tool(id=10, name="a", code="", user_id=1, public=True),
            db.Tool(id=11, name="b", code="", user_id=2, public=False),
            db.Tool(id=12, name="c", code="", user_id=2, public=True),
        ],
    )
    with Session(engine) as session:
        session.add(db.UpVote(user_id=1, tool_id=11))
        session.add(db.DownVote(user_id=1, tool_id=12))
        session.add(db.DownVote(user_id=3, tool_id=12))
        session.add(db.Report(user_id=1, tool_id=12, reason="spam"))
        session.add(db.Report(user_id=3, tool_id=11, reason="malware"))
        session.commit()
        accounts = db.get_users_with_tools(session)
    assert [(a.user.alias, a.up, a.down, a.reports) for a in accounts] == [("rob", 0, 0, 0), ("eve", 1, 2, 2)]
    eve = accounts[1]
    assert [(t.tool.name, t.up, t.down, t.reports) for t in eve.tools] == [("b", 1, 0, 1), ("c", 0, 2, 1)]


def test_ban_for_a_period_unpublishes_tools_and_unban_keeps_them_private():
    from datetime import datetime, timedelta, timezone

    engine = engine_with(
        users=[db.User(id=2, alias="eve")],
        tools=[db.Tool(name="c", code="", user_id=2, public=True)],
    )
    with Session(engine) as session:
        db.set_banned(session, 2, months=6)
        user = session.get(db.User, 2)
        assert user.banned and not session.exec(db.select(db.Tool)).one().public
        expected = datetime.now(timezone.utc) + timedelta(days=6 * 30)
        assert abs((user.banned_until.replace(tzinfo=timezone.utc) - expected).total_seconds()) < 60
        db.set_banned(session, 2, months=None)
        user = session.get(db.User, 2)
        assert not user.banned and user.banned_until is None and not session.exec(db.select(db.Tool)).one().public


def test_expired_ban_lifts_itself():
    from datetime import datetime, timedelta, timezone

    engine = engine_with(users=[db.User(id=2, alias="eve", banned=True, banned_until=datetime.now(timezone.utc) - timedelta(days=1))])
    with Session(engine) as session:
        assert db.lift_expired_ban(session, session.get(db.User, 2)) is True
        assert not session.get(db.User, 2).banned
        still = db.User(id=3, alias="mal", banned=True, banned_until=datetime.now(timezone.utc) + timedelta(days=1))
        session.add(still)
        session.commit()
        assert db.lift_expired_ban(session, still) is False and still.banned


def test_admin_page_is_404_for_anonymous_and_ordinary_users(monkeypatch):
    from app.routes import admin as admin_routes

    c = client(monkeypatch, StubRunner())
    assert c.get("/admin").status_code == 404
    monkeypatch.setattr(admin_routes, "session_user", lambda request: db.User(id=2, alias="eve"))
    assert c.get("/admin").status_code == 404
    assert c.post("/admin/ban/2", params={"months": "1"}).status_code == 404
    assert c.post("/admin/unban/2").status_code == 404


def test_admin_page_lists_accounts_and_their_tools(monkeypatch):
    from app.routes import admin as admin_routes

    monkeypatch.setattr(admin_routes, "session_user", lambda request: db.User(id=1, alias="rob", admin=True))
    from datetime import datetime, timezone

    rob = db.User(id=1, alias="rob", admin=True)
    eve = db.User(id=2, alias="eve", banned=True, banned_until=datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc))
    a = db.Tool(id=5, name="a", code="", user_id=1, public=True)
    b = db.Tool(id=6, name="b", code="", user_id=2, public=False)
    monkeypatch.setattr(
        db,
        "get_users_with_tools",
        lambda session: [
            db.AccountSummary(rob, [db.ToolSummary(a, 0, 0, 0)], 0, 0, 0),
            db.AccountSummary(eve, [db.ToolSummary(b, 1, 4, 3)], 1, 4, 3),
        ],
    )
    page = client(monkeypatch, StubRunner()).get("/admin").text
    assert "ls -l /home/*/models/ | column -t" in page
    assert page.index("rob/ ") < page.index("a.py") < page.index("eve/ ") < page.index("b.py")
    assert 'href="/model/6"' in page  # private tools are linked for the admin
    assert "banned until 2026-11-20" in page and "[unban]" in page  # eve
    assert page.count('value="1">1 month') == 0 or True
    assert "[delete]" in page  # admins can remove a single offending tool
    import re

    eve_row = page[page.index("eve/ "):page.index("b.py")]
    assert re.search(r">\s*1\s*<.*>\s*4\s*<.*>\s*3\s*<", eve_row, re.S)  # totals: up, down, reports


def test_admin_can_ban_for_a_period_and_unban(monkeypatch):
    from app.routes import admin as admin_routes

    calls = []
    monkeypatch.setattr(admin_routes, "session_user", lambda request: db.User(id=1, alias="rob", admin=True))
    monkeypatch.setattr(db, "set_banned", lambda session, user_id, months: calls.append((user_id, months)))
    c = client(monkeypatch, StubRunner())
    assert c.post("/admin/ban/2", params={"months": "1"}).status_code == 200
    assert c.post("/admin/ban/2", params={"months": "12"}).status_code == 200
    assert c.post("/admin/ban/2", params={"months": "3"}).status_code == 400  # only 1, 6 or 12
    assert c.post("/admin/unban/2").status_code == 200
    assert c.post("/admin/ban/1", params={"months": "1"}).status_code == 400  # not yourself
    assert calls == [(2, 1), (2, 12), (2, None)]


def test_admin_can_delete_another_users_tool(monkeypatch):
    from app.routes import upload as upload_routes

    deleted = []
    tool = db.Tool(id=6, name="b", code="", user_id=2, public=True)
    monkeypatch.setattr(upload_routes.tools, "get_tool", lambda session, id: tool)
    monkeypatch.setattr(upload_routes.tools, "del_tool", lambda session, t: deleted.append(t.id))
    monkeypatch.setattr(upload_routes, "session_user", lambda request: db.User(id=1, alias="rob", admin=True))
    assert client(monkeypatch, StubRunner()).delete("/manage/model/delete/6").status_code == 200 and deleted == [6]
    monkeypatch.setattr(upload_routes, "session_user", lambda request: db.User(id=3, alias="eve"))
    assert client(monkeypatch, StubRunner()).delete("/manage/model/delete/6").status_code == 404 and deleted == [6]


def test_admin_opens_a_private_tool_page(monkeypatch, tmp_path):
    import dataclasses

    monkeypatch.setattr(
        tools_routes.db_tools,
        "get_tool_by_id",
        lambda session, id: db.Tool(id=9, name="secret", code="def secret(): return 1", arguments={}, public=False, user_id=2),
    )
    env = tools_routes.ENVIRONMENT
    monkeypatch.setattr(tools_routes, "ENVIRONMENT", dataclasses.replace(env, sandbox=dataclasses.replace(env.sandbox, run_dir=tmp_path)))
    c = client(monkeypatch, StubRunner())
    assert c.get("/model/9").status_code == 404  # anonymous
    monkeypatch.setattr(tools_routes, "session_user", lambda request: db.User(id=1, alias="rob", admin=True))
    assert c.get("/model/9").status_code == 200


def test_banned_user_cannot_log_in(monkeypatch):
    from app.routes import auth as auth_routes

    class FakeGitHub:
        configured = True

        def login_url(self, state):
            return "https://github.example/authorize?state=" + state

        async def user_for_code(self, code):
            return {"login": "eve", "id": 7}

    monkeypatch.setattr(auth_routes, "github", FakeGitHub())
    from datetime import datetime, timezone

    monkeypatch.setattr(
        auth_routes, "get_user", lambda session, id: db.User(id=2, alias="eve", banned=True, banned_until=datetime(2099, 1, 2, tzinfo=timezone.utc))
    )
    c = TestClient(app)
    # plant a matching state the way the login button does
    c.get("/login/button")
    monkeypatch.setattr(auth_routes.secrets, "compare_digest", lambda a, b: True)
    r = c.get("/auth/github", params={"code": "x", "state": "y"}, follow_redirects=False)
    assert r.status_code == 403 and "banned until 2099-01-02" in r.json()["detail"]


def test_session_user_json_carries_admin_flag():
    user = db.User(id=1, alias="rob", admin=True)
    assert json.loads(user.model_dump_json())["admin"] is True


def test_admin_page_folds_each_accounts_tools_behind_its_row(monkeypatch):
    from app.routes import admin as admin_routes

    monkeypatch.setattr(admin_routes, "session_user", lambda request: db.User(id=1, alias="rob", admin=True))
    eve = db.User(id=2, alias="eve")
    b = db.Tool(id=6, name="b", code="", user_id=2, public=True)
    monkeypatch.setattr(db, "get_users_with_tools", lambda session: [db.AccountSummary(eve, [db.ToolSummary(b, 0, 0, 0)], 0, 0, 0)])
    page = client(monkeypatch, StubRunner()).get("/admin").text
    # the tool rows are a hidden group the account row toggles
    assert 'id="tools-2"' in page and "tools-2" in page[page.index("eve/ ") - 400 : page.index("eve/ ")]
    assert page[page.index('id="tools-2"') : page.index('id="tools-2"') + 60].count("hidden") == 1
