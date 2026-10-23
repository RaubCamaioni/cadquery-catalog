"""Tags are metadata beside the script: normalised, limited, filtered, and suggested from what is in use."""

import pytest

from app import metadata
from app.metadata import MetadataError
from app.metadata import tags


def form(*values):
    return {"tags.present": ["1"], "tags": list(values)}


def test_normalise():
    assert tags.normalise("  Kitchen Tools ") == "kitchen-tools"
    assert tags.normalise("M3") == "m3" and tags.normalise("c++") == "c++"
    for bad in ["", "   ", "-x", "a" * 31, "café", "a/b"]:
        with pytest.raises(MetadataError):
            tags.normalise(bad)


def test_parse_splits_commas_drops_duplicates_and_limits():
    assert tags.Tags().parse(form("Kitchen Tools, ", "kitchen-tools", "M3")) == ["kitchen-tools", "m3"]
    assert tags.Tags().parse({}) is None  # the editor was not on the page: keep what is stored
    assert tags.Tags().parse({"tags.present": ["1"]}) == []  # shown and emptied: clear
    with pytest.raises(MetadataError, match="10"):
        tags.Tags().parse(form(*[f"t{i}" for i in range(11)]))


def test_profane_tag_is_rejected():
    with pytest.raises(MetadataError, match="profanity"):
        tags.Tags().parse(form("shit"))
    assert tags.Tags().parse(form("screw")) == ["screw"]  # hardware words stay allowed


def test_save_replaces_and_load_batches(session_with_models):
    session, make = session_with_models
    a, b = make("a"), make("b")
    kind = tags.Tags()
    kind.save(session, a, ["x", "y"])
    session.commit()
    kind.save(session, a, ["y", "z"])
    session.commit()
    assert kind.load(session, [a, b]) == {a: ["y", "z"], b: []}
    assert kind.load(session, []) == {}


def test_suggest_counts_public_models_only(session_with_models):
    session, make = session_with_models
    kind = tags.Tags()
    for name, model_tags, public in [
        ("a", ["kitchen", "kettle"], True),
        ("b", ["kitchen"], True),
        ("c", ["kitchen", "knife"], False),
        ("d", ["m3"], True),
    ]:
        kind.save(session, make(name, public=public), model_tags)
    session.commit()
    assert tags.suggest(session, "k") == [("kitchen", 2), ("kettle", 1)]
    assert tags.suggest(session, "")[0] == ("kitchen", 2)
    assert tags.suggest(session, "K ") == [("kitchen", 2), ("kettle", 1)]
    assert tags.suggest(session, "_") == [] and tags.suggest(session, "%") == []  # wildcards match themselves


def test_apply_parses_everything_before_saving(session_with_models, monkeypatch):
    session, make = session_with_models
    model = make("a")

    class Broken:
        key = "broken"

        def parse(self, form):
            raise MetadataError("broken field")

    monkeypatch.setattr(metadata, "KINDS", [tags.Tags(), Broken()])
    with pytest.raises(MetadataError, match="broken"):
        metadata.apply(session, model, form("box"))
    session.commit()
    assert tags.Tags().load(session, [model]) == {model: []}


def test_load_all_and_absent_kinds_keep_values(session_with_models):
    session, make = session_with_models
    model = make("a")
    metadata.apply(session, model, form("box"))
    session.commit()
    metadata.apply(session, model, {"other": ["x"]})  # a form without the tags editor
    session.commit()
    assert metadata.load_all(session, [model])[model]["tags"] == ["box"]
