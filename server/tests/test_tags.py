import html

from sqlmodel import Session, SQLModel, create_engine

from app.models import tools as db
from app.routes import tools as tools_routes

from tests.test_tool_routes import StubRunner, client


def session_with(tools):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    for t in tools:
        session.add(t)
    session.commit()
    return session


def test_search_words_match_names_and_first_line_hashtags():
    session = session_with(
        [
            db.Tool(name="pdf_merge", code="", tags=["pdf", "merge", "pdf_merge"], public=True, user_id=1),
            db.Tool(name="pdf_split", code="", tags=["pdf", "split", "pdf_split"], public=True, user_id=1),
            db.Tool(name="image_crop", code="", tags=["image", "crop", "image_crop"], public=True, user_id=1),
        ]
    )
    names = lambda rows: sorted(name for _, name in rows)  # noqa: E731
    assert names(db.get_tools_by_tags(session, ["pdf"], 0, 50)) == ["pdf_merge", "pdf_split"]  # a hashtag
    assert names(db.get_tools_by_tags(session, ["crop"], 0, 50)) == ["image_crop"]  # a hashtag that is not in the name
    assert names(db.get_tools_by_tags(session, ["pdf", "split"], 0, 50)) == ["pdf_split"]  # every word must match


def test_tools_route_searches_with_the_typed_words(monkeypatch):
    calls = []

    def fake(session, tags, start, end):
        calls.append(tags)
        return [(i, f"pdf_tool{i}") for i in range(50)]  # a full page: the loader for the next one follows

    monkeypatch.setattr(db, "get_tools_by_tags", fake)
    r = client(monkeypatch, StubRunner()).post("/models?start=0&end=50", data={"search": "merge pdf"})
    assert r.status_code == 200 and calls == [["merge", "pdf"]]
    assert "merge pdf" in html.unescape(r.text)  # the infinite-scroll loader carries the words forward
    assert "tag-filters" not in r.text


def test_home_page_has_no_hashtag_checkboxes(monkeypatch):
    page = client(monkeypatch, StubRunner()).get("/").text
    assert 'name="tag"' not in page and "head -n1" not in page


def test_home_page_search_field_takes_any_typing(monkeypatch):
    from app.app import app
    from fastapi.testclient import TestClient

    page = TestClient(app).get("/").text
    assert "autofocus" in page.split('name="search"')[1].split(">")[0]  # focused on load
    assert 'document.addEventListener("keydown"' in page and "search.focus()" in page  # and on any key


def test_home_page_filters_as_you_type(monkeypatch):
    from app.app import app
    from fastapi.testclient import TestClient

    page = TestClient(app).get("/").text
    trigger = page.split('id="filter"')[1].split("hx-trigger=\"")[1].split('"')[0]
    assert "input delay:" in trigger and "search" in trigger and "Enter" not in trigger
