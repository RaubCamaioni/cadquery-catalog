"""catalog-admin apply-manifest: sets the owner's stored models' tags and categories from a manifest; a dry
run by default, a JSON backup of the previous values before anything is saved."""

import json

from app import admin_cli, metadata

OWNER = 49600918
MANIFEST = {
    "box": {"tags": ["box", "lid"], "categories": ["home/storage"]},
    "hook": {"tags": ["hook"], "categories": ["home/wall", "workshop/tool-storage"]},
    "gone": {"tags": ["x"], "categories": ["misc"]},
}


def seed(make):
    return {"box": make("box", user_id=OWNER), "hook": make("hook", user_id=OWNER), "other": make("box", user_id=5)}


def test_dry_run_reports_and_saves_nothing(session_with_models, tmp_path):
    session, make = session_with_models
    ids = seed(make)
    code, lines = admin_cli.apply_manifest(session, MANIFEST, OWNER, apply=False, backup_dir=tmp_path)
    assert code == 0
    assert any(line.startswith("box:") and "home/storage" in line for line in lines)
    assert any("not stored: gone" in line for line in lines)
    assert metadata.load_all(session, [ids["box"]])[ids["box"]] == {"tags": [], "categories": ["misc"], "description": ""}
    assert list(tmp_path.iterdir()) == []


def test_apply_saves_and_backs_up(session_with_models, tmp_path):
    session, make = session_with_models
    ids = seed(make)
    metadata.apply(session, ids["box"], {"tags.present": ["1"], "tags": ["old"]})
    session.commit()
    code, _ = admin_cli.apply_manifest(session, MANIFEST, OWNER, apply=True, backup_dir=tmp_path)
    assert code == 0
    loaded = metadata.load_all(session, [ids["box"], ids["hook"], ids["other"]])
    assert loaded[ids["box"]] == {"tags": ["box", "lid"], "categories": ["home/storage"], "description": ""}
    assert loaded[ids["hook"]]["categories"] == ["home/wall", "workshop/tool-storage"]
    assert loaded[ids["other"]] == {"tags": [], "categories": ["misc"], "description": ""}  # another user's model is never touched
    [backup] = list(tmp_path.iterdir())
    previous = json.loads(backup.read_text())
    assert previous[str(ids["box"])] == {"name": "box", "tags": ["old"], "categories": ["misc"], "description": ""}
    # running it again changes nothing and writes no second backup
    code, lines = admin_cli.apply_manifest(session, MANIFEST, OWNER, apply=True, backup_dir=tmp_path)
    assert code == 0 and len(list(tmp_path.iterdir())) == 1 and not any(line.startswith("box:") for line in lines)


def test_duplicate_owner_names_stop_everything(session_with_models, tmp_path):
    session, make = session_with_models
    seed(make)
    make("hook", user_id=OWNER)  # a second "hook" owned by the owner
    code, lines = admin_cli.apply_manifest(session, MANIFEST, OWNER, apply=True, backup_dir=tmp_path)
    assert code == 1 and any("hook" in line and "more than one" in line for line in lines)
    assert list(tmp_path.iterdir()) == []


def test_invalid_manifest_stops_before_any_change(session_with_models, tmp_path):
    session, make = session_with_models
    ids = seed(make)
    bad = {**MANIFEST, "hook": {"tags": ["hook"], "categories": ["home/nope"]}}
    code, lines = admin_cli.apply_manifest(session, bad, OWNER, apply=True, backup_dir=tmp_path)
    assert code == 1 and any("hook" in line and "unknown category" in line for line in lines)
    assert metadata.load_all(session, [ids["box"]])[ids["box"]]["tags"] == []


def test_manifest_descriptions_are_optional_and_left_alone_when_absent(session_with_models, tmp_path):
    session, make = session_with_models
    ids = seed(make)
    metadata.apply(session, ids["hook"], {"description.present": ["1"], "description": ["written on the site"]})
    session.commit()
    manifest = {**MANIFEST, "box": {**MANIFEST["box"], "description": "From the manifest."}}
    code, _ = admin_cli.apply_manifest(session, manifest, OWNER, apply=True, backup_dir=tmp_path)
    loaded = metadata.load_all(session, [ids["box"], ids["hook"]])
    assert code == 0 and loaded[ids["box"]]["description"] == "From the manifest."
    assert loaded[ids["hook"]]["description"] == "written on the site"  # no description in its entry: kept
