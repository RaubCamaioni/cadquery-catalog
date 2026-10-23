"""Tags and categories are set in the upload form and edited by the model's owner (or an admin)."""

import pytest
from fastapi.testclient import TestClient

from app import metadata
from app.app import app
from app.metadata.tags import Tags
from app.models import tools as db

from tests.test_auth_routes import github  # noqa: F401  (fixture)
from tests.test_upload_models import MODEL, BuildingRunner, logged_in, upload  # noqa: F401  (fixtures)
from tests.test_tool_routes import built

META = {"tags.present": "1", "tags": ["Box", "lid"], "categories.present": "1", "categories": ["home/storage"]}


def stored(name):
    with db.Session(db.engine) as session:
        model = session.exec(db.select(db.Tool).where(db.Tool.name == name)).first()
        return None if model is None else (model.id, metadata.load_all(session, [model.id])[model.id])


def post(c, monkeypatch, runner, name, data=None, url="/manage/model/upload"):
    from app.routes import tools as tools_routes

    monkeypatch.setattr(tools_routes, "runner", runner)
    code = MODEL.replace("demo_box", name)
    return c.post(url, files={"file": (f"{name}.py", code.encode(), "text/x-python")}, data=data or {})


def test_upload_stores_metadata(monkeypatch, logged_in):
    r = post(logged_in, monkeypatch, BuildingRunner(built()), "meta_box", META)
    assert r.status_code == 200, r.text
    assert stored("meta_box")[1] == {"tags": ["box", "lid"], "categories": ["home/storage"]}


def test_upload_without_metadata_is_miscellaneous(monkeypatch, logged_in):
    assert post(logged_in, monkeypatch, BuildingRunner(built()), "plain_box").status_code == 200
    assert stored("plain_box")[1] == {"tags": [], "categories": ["misc"]}


def test_bad_metadata_rejects_upload_before_building(monkeypatch, logged_in):
    runner = BuildingRunner(built())
    r = post(logged_in, monkeypatch, runner, "bad_meta", {"categories.present": "1", "categories": ["home/cooking"]})
    assert r.status_code == 400 and "unknown category" in r.json()["detail"]
    assert runner.calls == [] and stored("bad_meta") is None


def test_update_without_metadata_keeps_it(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "kept_box", META)
    model_id, _ = stored("kept_box")
    r = post(logged_in, monkeypatch, BuildingRunner(built()), "kept_box", url=f"/manage/model/update/{model_id}")
    assert r.status_code == 200, r.text
    assert stored("kept_box")[1] == {"tags": ["box", "lid"], "categories": ["home/storage"]}


def test_owner_edits_metadata_and_gets_the_display(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "edit_box", META)
    model_id, _ = stored("edit_box")
    r = logged_in.post(
        f"/manage/model/{model_id}/metadata",
        data={"tags.present": "1", "tags": ["crate"], "categories.present": "1", "categories": ["home/kitchen", "workshop/tool-storage"]},
    )
    assert r.status_code == 200, r.text
    assert "#crate" in r.text and "Kitchen" in r.text and "Workshop › Tool Storage" in r.text
    assert stored("edit_box")[1] == {"tags": ["crate"], "categories": ["home/kitchen", "workshop/tool-storage"]}
    # only the categories editor sent: the tags stay
    logged_in.post(f"/manage/model/{model_id}/metadata", data={"categories.present": "1"})
    assert stored("edit_box")[1] == {"tags": ["crate"], "categories": ["misc"]}


def test_edit_form_shows_both_editors_with_current_values(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "form_box", META)
    model_id, _ = stored("form_box")
    page = logged_in.get(f"/manage/model/{model_id}/metadata/edit").text
    assert 'name="tags.present"' in page and 'name="categories.present"' in page
    assert 'value="box"' in page and 'value="home/storage"' in page and "[save]" in page and "[cancel]" in page


def test_bad_edit_is_a_400_and_changes_nothing(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "keep_on_error", META)
    model_id, _ = stored("keep_on_error")
    r = logged_in.post(
        f"/manage/model/{model_id}/metadata",
        data={"tags.present": "1", "tags": ["new"], "categories.present": "1", "categories": ["misc", "home/kitchen"]},
    )
    assert r.status_code == 400 and "misc" in r.json()["detail"]
    assert stored("keep_on_error")[1]["tags"] == ["box", "lid"]


def test_someone_elses_model_is_a_404_unless_admin(monkeypatch, logged_in):
    with db.Session(db.engine) as session:
        other = db.Tool(name="not_mine", code="", user_id=777, public=True)
        session.add(other)
        session.commit()
        other_id = other.id
    data = {"tags.present": "1", "tags": ["x"]}
    assert logged_in.post(f"/manage/model/{other_id}/metadata", data=data).status_code == 404
    assert logged_in.get(f"/manage/model/{other_id}/metadata/edit").status_code == 404
    assert TestClient(app).post(f"/manage/model/{other_id}/metadata", data=data).status_code == 404  # logged out
    # an admin may edit any model; the logged-in user's id is the one their own upload is stored under
    post(logged_in, monkeypatch, BuildingRunner(built()), "mine_box")
    with db.Session(db.engine) as session:
        my_id = session.get(db.Tool, stored("mine_box")[0]).user_id
    set_admin(my_id, True)
    try:
        assert logged_in.post(f"/manage/model/{other_id}/metadata", data=data).status_code == 200
    finally:
        set_admin(my_id, False)


def set_admin(user_id, admin):
    with db.Session(db.engine) as session:
        user = db.get_user(session, user_id)
        user.admin = admin
        session.add(user)
        session.commit()


def make_public(model_id):
    with db.Session(db.engine) as session:
        model = session.get(db.Tool, model_id)
        model.public = True
        session.add(model)
        session.commit()


def test_display_route_for_cancel(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "view_box", META)
    model_id, _ = stored("view_box")
    make_public(model_id)  # uploads start private: a visitor could not see it
    r = TestClient(app).get(f"/model/{model_id}/metadata")
    assert r.status_code == 200 and "#box" in r.text and "Storage" in r.text and "[edit]" not in r.text
    assert "[edit]" in logged_in.get(f"/model/{model_id}/metadata").text  # the owner gets the button


def test_suggest_route(monkeypatch, logged_in):
    with db.Session(db.engine) as session:
        model = db.Tool(name="suggested", code="", user_id=1, public=True)
        session.add(model)
        session.commit()
        Tags().save(session, model.id, ["zebra-stripe"])
        session.commit()
    r = TestClient(app).get("/tags/suggest", params={"q": "zeb"})
    assert r.status_code == 200 and '<option value="zebra-stripe">' in r.text and "zebra-stripe · 1" in r.text


@pytest.mark.xfail(reason="category pages arrive in Task 7", strict=True)
def test_cleared_categories_fall_back_to_misc_page(monkeypatch, logged_in):
    post(logged_in, monkeypatch, BuildingRunner(built()), "cleared_box", META)
    model_id, _ = stored("cleared_box")
    with db.Session(db.engine) as session:
        model = session.get(db.Tool, model_id)
        model.public = True
        session.add(model)
        session.commit()
    logged_in.post(f"/manage/model/{model_id}/metadata", data={"categories.present": "1"})
    assert "cleared_box" in TestClient(app).get("/c/misc").text
