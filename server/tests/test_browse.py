"""Browsing by category: /c/<category> and /c/<category>/<subcategory> list the public models filed there
(extras included, unfiled ones under Miscellaneous), and the front page shows the tree with counts."""

import html
import re

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.metadata.categories import Categories
from app.models import tools as db
from app.routes import browse
from app.routes import tools as tools_routes

from tests.test_tool_routes import StubRunner


@pytest.fixture(scope="module")
def models():
    """br_a: home/kitchen + workshop/tool-storage; br_b: home/bathroom; br_c: private, home/kitchen; br_d: none."""
    ids = {}
    with db.Session(db.engine) as session:
        for name, paths, public in [
            ("br_a", ["home/kitchen", "workshop/tool-storage"], True),
            ("br_b", ["home/bathroom"], True),
            ("br_c", ["home/kitchen"], False),
            ("br_d", None, True),
        ]:
            model = db.Tool(name=name, code="", user_id=1, public=public)
            session.add(model)
            session.commit()
            if paths is not None:
                Categories().save(session, model.id, paths)
                session.commit()
            ids[name] = model.id
    return ids


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(tools_routes, "runner", StubRunner())
    return TestClient(app)


def listed(client, category=None, search=""):
    """The br_* names the infinite list shows for a category (other tests share this database)."""
    data = {"search": search, **({"category": category} if category is not None else {})}
    page = client.post("/models?start=0&end=500", data=data).text
    return {name for name in re.findall(r'<span class="block truncate px-1">([^<]+)</span>', page) if name.startswith("br_")}


def test_category_lists(client, models):
    assert listed(client, "home") == {"br_a", "br_b"}
    assert listed(client, "home/kitchen") == {"br_a"}  # br_c is private
    assert listed(client, "workshop/tool-storage") == {"br_a"}  # filed there as an extra
    assert listed(client, "misc") == {"br_d"}
    assert listed(client, "home/kitchen", search="br_") == {"br_a"}  # search within the category
    assert listed(client, "nope") == set()
    assert listed(client) >= {"br_a", "br_b", "br_d"}


def test_category_pages_exist_only_for_the_tree(client, models):
    assert client.get("/c/home").status_code == 200 and client.get("/c/home/kitchen").status_code == 200
    assert client.get("/c/misc").status_code == 200
    for missing in ["/c/nope", "/c/home/nope", "/c/misc/x", "/c/home/kitchen/x"]:
        assert client.get(missing).status_code == 404, missing


def test_category_page_has_breadcrumb_description_and_scoped_list(client, models):
    page = client.get("/c/home/kitchen").text
    assert 'href="/c/home"' in page and ">Kitchen<" in page
    assert "Cooking, baking, food storage and serving." in page
    assert '<input type="hidden" name="category" value="home/kitchen">' in page  # the search stays inside
    assert '"category": "home/kitchen"' in page  # and so does the infinite list's loader


def test_counts_ignore_private_models(models):
    with db.Session(db.engine) as session:
        counts = browse.category_counts(session)
    with db.Session(db.engine) as session:  # counts include other tests' public models: compare with the list
        kitchen = db.search_models(session, [], 0, 10_000, category="home/kitchen")
    assert counts["home/kitchen"] == len(kitchen)
    assert models["br_c"] not in {id for id, _ in kitchen}
    assert counts["home"] >= 2 and counts["misc"] >= 1


def test_index_shows_the_bar_in_yaml_order(client, models):
    page = client.get("/").text
    bar = page.split('id="category-bar"')[1].split("</nav>")[0]
    names = re.findall(r'<summary[^>]*>([^<(]+)', bar)
    assert [html.unescape(n).strip() for n in names] == ["Home", "Office & Desk", "Workshop", "Hardware & Electronics", "Outdoor & Garage", "Hobbies"]
    assert 'href="/c/home/kitchen"' in bar and 'href="/c/misc"' in bar


def test_index_takes_a_search_from_the_url(client, models):
    page = client.get("/", params={"search": "kitchen"}).text
    assert 'value="kitchen"' in page.split('name="search"')[1].split(">")[0]
    assert '"search": "kitchen"' in page  # the first page of the list is filtered too


def test_search_from_the_url_cannot_break_the_loader(client, models):
    page = client.get("/", params={"search": "\"}' x=\"<b>"}).text
    loader = page.split('hx-trigger="revealed"')[1].split(">")[0]
    assert "<b>" not in page.split('id="tool-list"')[1].split("</ul>")[0]
    assert "x=" not in loader.split("hx-vals=")[0]
