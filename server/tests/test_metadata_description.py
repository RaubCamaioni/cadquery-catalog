"""A model's description: plain text beside the script, at most 1000 characters, line breaks kept."""

import pytest

from app import metadata
from app.metadata import MetadataError
from app.metadata.description import MAX_LENGTH, Description


def parse(text):
    return Description().parse({"description.present": ["1"], "description": [text]})


def test_parse_trims_and_normalises_line_breaks():
    assert parse("  A scoop.\r\nHolds 30 ml.  ") == "A scoop.\nHolds 30 ml."
    assert parse("   ") == ""
    assert Description().parse({}) is None  # the box was not on the page: keep what is stored
    assert Description().parse({"description.present": ["1"]}) == ""


def test_parse_limits():
    assert len(parse("x" * MAX_LENGTH)) == MAX_LENGTH == 1000
    with pytest.raises(MetadataError, match="1000"):
        parse("x" * (MAX_LENGTH + 1))
    with pytest.raises(MetadataError, match="profanity"):
        parse("this is shit")


def test_save_and_load(session_with_models):
    session, make = session_with_models
    a, b = make("a"), make("b")
    kind = Description()
    kind.save(session, a, "first")
    session.commit()
    kind.save(session, a, "second")
    session.commit()
    assert kind.load(session, [a, b]) == {a: "second", b: ""}
    kind.save(session, a, "")
    session.commit()
    assert kind.load(session, [a]) == {a: ""}


def test_registered_after_the_others():
    assert [kind.key for kind in metadata.KINDS] == ["tags", "categories", "description"]


def test_deleted_with_the_model(session_with_models):
    from app.models import tools as db

    session, make = session_with_models
    model = make("a")
    Description().save(session, model, "text")
    session.commit()
    db.del_tool(session, session.get(db.Tool, model))
    assert Description().load(session, [model]) == {model: ""}
