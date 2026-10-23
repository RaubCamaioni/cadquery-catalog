import html

from app.models import tools as db
from app.metadata.categories import Categories
from app.metadata.tags import Tags

from tests.test_tool_routes import StubRunner, client


def seeded(session_with_models):
    """pdf_merge [pdf, merge], pdf_split [pdf, split], image_crop [image, crop] public; private_pdf [pdf] private."""
    session, make = session_with_models
    kind = Tags()
    for name, model_tags, public in [
        ("pdf_merge", ["pdf", "merge"], True),
        ("pdf_split", ["pdf", "split"], True),
        ("image_crop", ["image", "crop"], True),
        ("private_pdf", ["pdf"], False),
    ]:
        kind.save(session, make(name, public=public), model_tags)
    session.commit()
    return session, make


def names(rows):
    return sorted(name for _, name in rows)


def test_search_by_name_tag_and_prefix(session_with_models):
    s, _ = seeded(session_with_models)
    assert names(db.search_models(s, ["pdf"], 0, 50)) == ["pdf_merge", "pdf_split"]  # a tag; never the private one
    assert names(db.search_models(s, ["crop"], 0, 50)) == ["image_crop"]  # a tag that is not in the name
    assert names(db.search_models(s, ["pdf", "spl"], 0, 50)) == ["pdf_split"]  # every word; the last by prefix
    assert names(db.search_models(s, ["mer", "pdf"], 0, 50)) == ["pdf_merge"]  # a name substring
    assert names(db.search_models(s, ["PDF"], 0, 50)) == ["pdf_merge", "pdf_split"]  # case-insensitive
    assert names(db.search_models(s, ["cro", "image"], 0, 50)) == ["image_crop"]  # "cro" is in the name
    assert names(db.search_models(s, [], 0, 50)) == ["image_crop", "pdf_merge", "pdf_split"]


def test_search_escapes_like_wildcards(session_with_models):
    s, _ = seeded(session_with_models)
    # unescaped, "p_f" would match "pdf" and "%" everything; escaped they match only themselves
    assert db.search_models(s, ["%"], 0, 50) == [] and db.search_models(s, ["p_f"], 0, 50) == []
    assert names(db.search_models(s, ["pdf_m"], 0, 50)) == ["pdf_merge"]  # a real underscore still matches


def test_search_within_category(session_with_models):
    s, make = seeded(session_with_models)
    kind = Categories()
    rows = dict((name, id) for id, name in db.search_models(s, [], 0, 50))
    kind.save(s, rows["pdf_merge"], ["office/desk"])
    kind.save(s, rows["pdf_split"], ["home/kitchen", "office/desk"])
    s.commit()
    assert names(db.search_models(s, ["pdf"], 0, 50, category="office")) == ["pdf_merge", "pdf_split"]
    assert names(db.search_models(s, [], 0, 50, category="home/kitchen")) == ["pdf_split"]
    assert names(db.search_models(s, [], 0, 50, category="misc")) == ["image_crop"]
    assert db.search_models(s, [], 0, 50, category="nope") == []


def test_line_one_is_no_longer_read_as_tags():
    tool = db.create_tool(1, "demo", "# a, b\n\n\ndef demo(x: int = 1) -> int:\n    return x\n")
    assert "tags" not in db.Tool.model_fields and tool.code.startswith("# a, b\n")  # kept as a plain comment


def test_tools_route_searches_with_the_typed_words(monkeypatch):
    calls = []

    def fake(session, words, start, end, category=None):
        calls.append(words)
        return [(i, f"pdf_tool{i}") for i in range(50)]  # a full page: the loader for the next one follows

    monkeypatch.setattr(db, "search_models", fake)
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
