"""Tags used to be a JSON column on the tool row, filled from line 1 with the model name appended; the first
start of the metadata version copies them into ModelTag once."""

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import app.metadata  # noqa: F401  (registers the metadata tables)
from app.metadata.tags import Tags
from app.models import tools as db


def old_database(tmp_path, rows):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE tool ADD COLUMN tags JSON"))
        for id, name, tags in rows:
            conn.execute(
                text("INSERT INTO tool (id, name, code, arguments, tags, usage, preview_svg, public, annonymous, user_id) "
                     "VALUES (:id, :name, '', '{}', :tags, 0, '', 1, 1, 1)"),
                {"id": id, "name": name, "tags": tags},
            )
    return engine


def test_copy_json_tags_runs_once(tmp_path):
    engine = old_database(tmp_path, [(1, "demo", '["box", "lid", "AA", "demo"]'), (2, "bare", None), (3, "odd", '["ok", "a/b"]')])
    assert db.copy_json_tags(engine) == 4  # box, lid, aa; ok (a/b is not a valid tag and is skipped)
    with Session(engine) as session:
        assert Tags().load(session, [1, 2, 3]) == {1: ["box", "lid", "aa"], 2: [], 3: ["ok"]}
    assert db.copy_json_tags(engine) == 0  # ModelTag is no longer empty: never again


def test_fresh_database_has_nothing_to_copy(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    SQLModel.metadata.create_all(engine)
    assert db.copy_json_tags(engine) == 0
