"""Categories: up to three leaf paths from categories.yaml, primary first; anything unfiled is Miscellaneous."""

import pytest
from sqlmodel import select

from app import metadata
from app.metadata import MetadataError
from app.metadata import categories as categories_kind
from app.models.tools import Tool


def parse(*paths):
    return categories_kind.Categories().parse({"categories.present": ["1"], "categories": list(paths)})


def test_parse_valid_and_ordered():
    assert parse("workshop/tool-storage", "home/storage") == ["workshop/tool-storage", "home/storage"]
    assert parse() == [] and parse("misc") == ["misc"]
    assert categories_kind.Categories().parse({}) is None


@pytest.mark.parametrize(
    "paths, message",
    [
        (("home/kitchen", "home/kitchen"), "duplicate"),
        (("home/kitchen", "home/bathroom", "home/decor", "home/storage"), "3"),
        (("home/cooking",), "unknown"),
        (("home",), "unknown"),
        (("misc", "home/kitchen"), "misc"),
    ],
)
def test_parse_rejects(paths, message):
    with pytest.raises(MetadataError, match=message):
        parse(*paths)


def test_unknown_lists_the_valid_paths():
    with pytest.raises(MetadataError) as err:
        parse("home/cooking")
    assert "home/kitchen" in str(err.value) and "misc" in str(err.value)


def test_effective_falls_back_to_misc():
    assert categories_kind.effective([]) == ["misc"]
    assert categories_kind.effective(["gone/away"]) == ["misc"]
    assert categories_kind.effective(["gone/away", "home/kitchen"]) == ["home/kitchen"]


def test_save_and_load_effective(session_with_models):
    session, make = session_with_models
    a, b = make("a"), make("b")
    kind = categories_kind.Categories()
    kind.save(session, a, ["workshop/tool-storage", "home/storage"])
    session.commit()
    assert kind.load(session, [a, b]) == {a: ["workshop/tool-storage", "home/storage"], b: ["misc"]}
    kind.save(session, a, [])
    session.commit()
    assert kind.load(session, [a]) == {a: ["misc"]}


def test_model_ids_in_counts_unfiled_models_as_misc(session_with_models):
    session, make = session_with_models
    kind = categories_kind.Categories()
    a, b, c = make("a"), make("b"), make("c")
    kind.save(session, a, ["home/kitchen"])
    kind.save(session, c, ["gone/away"])  # stored before the tree lost that slug
    session.commit()

    def ids(paths):
        return set(session.exec(select(Tool.id).where(Tool.id.in_(categories_kind.model_ids_in(paths)))).all())

    assert ids(["misc"]) == {b, c}
    assert ids(["home/kitchen"]) == {a}
    assert ids(["home/kitchen", "misc"]) == {a, b, c}
    assert ids(["home/bathroom"]) == set()


def test_categories_are_registered_after_tags():
    assert [kind.key for kind in metadata.KINDS][:2] == ["tags", "categories"]
