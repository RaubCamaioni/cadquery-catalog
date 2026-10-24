"""Models are created and edited from the profile in one dialog: the file (required to create, optional to edit),
the description, the tags and the categories. Only the owner (or an admin, for metadata) may edit."""

from fastapi.testclient import TestClient

from app import metadata
from app.app import app
from app.metadata.tags import Tags
from app.models import tools as db
from sandboxcore.host import Outcome
from sandboxcore.host.podman import RunResult

from tests.test_auth_routes import github  # noqa: F401  (fixture)
from tests.test_upload_models import MODEL, BuildingRunner, logged_in  # noqa: F401  (fixtures)
from tests.test_tool_routes import StubRunner, built

META = {
    "description.present": "1",
    "description": "A box.\r\nWith a lid.",
    "tags.present": "1",
    "tags": ["Box", "lid"],
    "categories.present": "1",
    "categories": ["home/storage"],
}
STORED_META = {"tags": ["box", "lid"], "categories": ["home/storage"], "description": "A box.\nWith a lid."}
NO_META = {"tags": [], "categories": ["misc"], "description": ""}


def stored(name):
    with db.Session(db.engine) as session:
        model = session.exec(db.select(db.Tool).where(db.Tool.name == name)).first()
        return None if model is None else (model.id, metadata.load_all(session, [model.id])[model.id])


def code_of(model_id):
    with db.Session(db.engine) as session:
        return session.get(db.Tool, model_id).code


def post(c, monkeypatch, runner, name, data=None, url="/manage/model/upload", file=True):
    from app.routes import tools as tools_routes
    from sandboxcore.host import Sandbox

    monkeypatch.setattr(tools_routes, "sandbox", Sandbox(tools_routes.ENVIRONMENT.sandbox, runner=runner))
    code = MODEL.replace("demo_box", name)
    files = {"file": (f"{name}.py", code.encode(), "text/x-python")} if file else {"file": ("", b"", "application/octet-stream")}
    return c.post(url, files=files, data=data or {})


def set_user(user_id, **fields):
    with db.Session(db.engine) as session:
        user = db.get_user(session, user_id)
        for key, value in fields.items():
            setattr(user, key, value)
        session.add(user)
        session.commit()


def my_id(c, monkeypatch):
    post(c, monkeypatch, BuildingRunner(built()), "whoami_box")
    with db.Session(db.engine) as session:
        return session.get(db.Tool, stored("whoami_box")[0]).user_id


def make_public(model_id):
    with db.Session(db.engine) as session:
        model = session.get(db.Tool, model_id)
        model.public = True
        session.add(model)
        session.commit()


# --- create ------------------------------------------------------------------------------------------------------


def test_create_stores_the_file_and_all_metadata(monkeypatch, logged_in):
    r = post(logged_in, monkeypatch, BuildingRunner(built()), "meta_box", META)
    assert r.status_code == 200, r.text
    assert stored("meta_box")[1] == STORED_META


def test_create_without_metadata_is_miscellaneous(monkeypatch, logged_in):
    assert post(logged_in, monkeypatch, BuildingRunner(built()), "plain_box").status_code == 200
    assert stored("plain_box")[1] == NO_META


def test_bad_metadata_rejects_create_before_building(monkeypatch, logged_in):
    runner = BuildingRunner(built())
    r = post(logged_in, monkeypatch, runner, "bad_meta", {"categories.present": "1", "categories": ["home/cooking"]})
    assert r.status_code == 400 and "unknown category" in r.json()["detail"]
    assert runner.calls == [] and stored("bad_meta") is None


def test_create_needs_a_file(monkeypatch, logged_in):
    r = post(logged_in, monkeypatch, BuildingRunner(built()), "no_file", META, file=False)
    assert r.status_code == 400 and "file" in r.json()["detail"].lower()


# --- edit --------------------------------------------------------------------------------------------------------


def test_edit_without_a_file_saves_metadata_and_builds_nothing(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "info_box")
    model_id, _ = stored("info_box")
    before = code_of(model_id)
    runner = BuildingRunner(built())
    r = post(logged_in, monkeypatch, runner, "info_box", META, url=f"/manage/model/update/{model_id}", file=False)
    assert r.status_code == 200, r.text
    assert runner.calls == [] and code_of(model_id) == before
    assert stored("info_box")[1] == STORED_META


def test_edit_with_a_file_replaces_the_code_and_saves_metadata(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "swap_box")
    model_id, _ = stored("swap_box")
    runner = BuildingRunner(built())
    r = post(logged_in, monkeypatch, runner, "swap_box", META, url=f"/manage/model/update/{model_id}")
    assert r.status_code == 200 and len(runner.calls) == 1
    assert stored("swap_box")[1] == STORED_META


def test_edit_with_only_a_file_keeps_metadata(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "kept_box", META)
    model_id, _ = stored("kept_box")
    r = post(logged_in, monkeypatch, BuildingRunner(built()), "kept_box", url=f"/manage/model/update/{model_id}")
    assert r.status_code == 200, r.text
    assert stored("kept_box")[1] == STORED_META


def test_failed_build_on_edit_saves_nothing(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "fail_box", META)
    model_id, _ = stored("fail_box")
    before = code_of(model_id)
    failing = StubRunner(RunResult(Outcome.OK, results="Export Error: NotAModel: a model must return a cadquery Workplane"))
    new_meta = {**META, "tags": ["changed"]}
    r = post(logged_in, monkeypatch, failing, "fail_box", new_meta, url=f"/manage/model/update/{model_id}")
    assert r.status_code == 400 and "Model Build Failed" in r.json()["detail"]
    assert code_of(model_id) == before and stored("fail_box")[1] == STORED_META


def test_bad_metadata_on_edit_changes_nothing(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "keep_on_error", META)
    model_id, _ = stored("keep_on_error")
    bad = {**META, "tags": ["new"], "categories": ["misc", "home/kitchen"]}
    r = post(logged_in, monkeypatch, BuildingRunner(built()), "keep_on_error", bad, url=f"/manage/model/update/{model_id}", file=False)
    assert r.status_code == 400 and "misc" in r.json()["detail"]
    assert stored("keep_on_error")[1] == STORED_META


def test_someone_elses_model(monkeypatch, logged_in):
    with db.Session(db.engine) as session:
        other = db.Tool(name="not_mine", code="", user_id=777, public=True)
        session.add(other)
        session.commit()
        other_id = other.id
    data = {"tags.present": "1", "tags": ["x"]}
    url = f"/manage/model/update/{other_id}"
    assert post(logged_in, monkeypatch, BuildingRunner(built()), "not_mine", data, url=url, file=False).status_code == 404
    assert logged_in.get(f"/manage/model/{other_id}/edit").status_code == 404
    assert TestClient(app).get(f"/manage/model/{other_id}/edit").status_code == 404  # logged out
    # an admin may edit any model's metadata, but never replace someone else's code
    me = my_id(logged_in, monkeypatch)
    set_user(me, admin=True)
    try:
        assert logged_in.get(f"/manage/model/{other_id}/edit").status_code == 200
        assert post(logged_in, monkeypatch, BuildingRunner(built()), "not_mine", data, url=url, file=False).status_code == 200
        assert post(logged_in, monkeypatch, BuildingRunner(built()), "not_mine", data, url=url).status_code == 404
    finally:
        set_user(me, admin=False)


def test_banned_owner_cannot_edit(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "banned_box", META)
    model_id, _ = stored("banned_box")
    me = my_id(logged_in, monkeypatch)
    set_user(me, banned=True)
    try:
        assert logged_in.get(f"/manage/model/{model_id}/edit").status_code == 404
        r = post(logged_in, monkeypatch, BuildingRunner(built()), "banned_box", {**META, "tags": ["changed"]},
                 url=f"/manage/model/update/{model_id}", file=False)
        assert r.status_code == 403
        assert stored("banned_box")[1] == STORED_META
    finally:
        set_user(me, banned=False)


# --- the dialog --------------------------------------------------------------------------------------------------


def test_edit_dialog_is_filled_with_the_current_values(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "form_box", META)
    model_id, _ = stored("form_box")
    page = logged_in.get(f"/manage/model/{model_id}/edit").text
    assert f'hx-post="/manage/model/update/{model_id}"' in page and "edit form_box.py" in page
    assert 'value="box"' in page and 'value="home/storage"' in page and "A box.\nWith a lid.</textarea>" in page
    assert 'name="file"' in page and "required" not in page.split('name="file"')[1].split(">")[0]
    assert "replaces the code" not in page and "[&lt;]" not in page and "<datalist" not in page
    assert 'title="click to make this the primary category"' in page and "home/kitchen" in page  # the choices
    assert "[save]" in page and "[cancel]" in page
    assert page.index("[cancel]") < page.index("[save]")  # [save] is the rightmost button
    assert page.count('class="meta-add') == 2 and page.count('class="meta-chips"') == 2  # [+] and a box per editor
    assert 'data-empty="no tags yet"' in page


def test_create_dialog_is_empty_and_needs_a_file(monkeypatch, logged_in):
    page = logged_in.get("/manage/model/create").text
    assert 'hx-post="/manage/model/upload"' in page and "[create]" in page
    assert page.index("[cancel]") < page.index("[create]")
    assert "required" in page.split('name="file"')[1].split(">")[0]
    assert 'name="tags.present"' in page and 'name="categories.present"' in page and 'name="description.present"' in page
    assert TestClient(app).get("/manage/model/create").status_code == 404


def test_profile_rows_show_the_category_and_open_the_dialog(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "row_box", META)
    model_id, _ = stored("row_box")
    rows = logged_in.post("/user/models").text
    row = rows.split(f">row_box.py<")[1].split("</li>")[0]
    assert f'hx-get="/manage/model/{model_id}/edit"' in row and "[edit]" in row
    assert "Home › Storage" not in rows  # categories are shown and changed in the dialog, not the table
    assert 'hx-get="/manage/model/create"' in rows and "[create]" in rows
    assert "/manage/model/update/" not in rows  # no one-click file replacement any more


# --- the model page ----------------------------------------------------------------------------------------------


def test_model_page_shows_description_categories_and_tags_without_editing(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "page_box", {**META, "categories": ["home/kitchen", "workshop/tool-storage"]})
    model_id, _ = stored("page_box")
    make_public(model_id)
    page = logged_in.get(f"/model/{model_id}").text  # even the owner gets no editor here
    meta = page.split('id="model-meta"')[1].split("</div>\n            </div>")[0]
    assert '<p class="meta-description">A box.\nWith a lid.</p>' in meta
    assert 'href="/c/home"' in meta and 'href="/c/home/kitchen"' in meta and 'href="/c/workshop/tool-storage"' in meta
    assert 'href="/?search=box"' in meta and "#lid" in meta
    assert "[edit]" not in page and "/metadata" not in page


def test_model_without_metadata_shows_miscellaneous(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "misc_box")
    model_id, _ = stored("misc_box")
    page = logged_in.get(f"/model/{model_id}").text
    assert 'href="/c/misc"' in page and ">Miscellaneous<" in page and '<p class="meta-description">' not in page


def test_the_v050_edit_routes_are_gone(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "old_routes")
    model_id, _ = stored("old_routes")
    assert logged_in.post(f"/manage/model/{model_id}/metadata", data={"tags.present": "1"}).status_code in (404, 405)
    assert logged_in.get(f"/manage/model/{model_id}/metadata/edit").status_code == 404
    assert logged_in.get(f"/model/{model_id}/metadata").status_code == 404


def test_cleared_categories_fall_back_to_misc_page(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "cleared_box", META)
    model_id, _ = stored("cleared_box")
    make_public(model_id)
    post(logged_in, monkeypatch, BuildingRunner(built()), "cleared_box", {"categories.present": "1"},
         url=f"/manage/model/update/{model_id}", file=False)
    listing = TestClient(app).post("/models?start=0&end=1000", data={"search": "cleared_box", "category": "misc"})
    assert ">cleared_box<" in listing.text


def test_suggest_route(monkeypatch, logged_in):
    with db.Session(db.engine) as session:
        model = db.Tool(name="suggested", code="", user_id=1, public=True)
        session.add(model)
        session.commit()
        Tags().save(session, model.id, ["zebra-stripe"])
        session.commit()
    r = TestClient(app).get("/tags/suggest", params={"q": "zeb"})
    assert r.status_code == 200 and r.json() == [{"tag": "zebra-stripe", "count": 1}]
