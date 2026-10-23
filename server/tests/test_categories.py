"""The category tree: the shipped categories.yaml loads, and a malformed tree stops the app instead of serving."""

import pytest

from app import categories

SUB = "{slug: a, name: A, description: d}"
MISC = "- {slug: misc, name: M, description: d}"


def test_shipped_tree_loads():
    assert [c.slug for c in categories.TREE] == ["home", "office", "workshop", "hardware", "outdoor", "hobbies", "misc"]
    assert sum(len(c.subcategories) for c in categories.TREE) == 22
    assert categories.label("home/kitchen") == "Home › Kitchen" and categories.label("misc") == "Miscellaneous"
    assert categories.is_leaf("home/kitchen") and categories.is_leaf("misc") and not categories.is_leaf("home")
    assert not categories.is_leaf("home/nope") and not categories.is_leaf("misc/x")
    assert "workshop/tool-storage" in categories.paths_under("workshop") and categories.paths_under("misc") == ["misc"]
    assert categories.paths_under("nope") == []
    assert categories.leaves()[0] == ("home/kitchen", "Home › Kitchen") and categories.leaves()[-1] == ("misc", "Miscellaneous")
    assert categories.find("home").name == "Home" and categories.find("home/kitchen").name == "Kitchen"
    assert categories.find("home/kitchen").path == "home/kitchen" and categories.find("nope") is None


@pytest.mark.parametrize(
    "bad, message",
    [
        (f"- {{slug: Home, name: H, description: d, subcategories: [{SUB}]}}\n{MISC}", "slug"),
        (f"- {{slug: home, name: H, description: d, subcategories: []}}\n{MISC}", "subcategories"),
        (f"- {{slug: home, name: H, description: d, subcategories: [{SUB}, {SUB}]}}\n{MISC}", "duplicate"),
        (f"- {{slug: home, name: H, description: d, subcategories: [{SUB}]}}\n- {{slug: home, name: H, description: d, subcategories: [{SUB}]}}\n{MISC}", "duplicate"),
        (f"- {{slug: home, name: H, description: d, subcategories: [{SUB}]}}", "misc"),
        (f"- {{slug: home, name: H, description: d, subcategories: [{SUB}]}}\n- {{slug: misc, name: M, description: d, subcategories: [{SUB}]}}", "misc"),
        (f"- {{slug: home, name: H, subcategories: [{SUB}]}}\n{MISC}", "description"),
        (f"- {{slug: home, name: H, description: d, subcategories: [{{slug: a, name: A, description: d, subcategories: [{SUB}]}}]}}\n{MISC}", "nest"),
        ("just text", "list"),
    ],
)
def test_bad_trees_are_rejected(bad, message):
    with pytest.raises(categories.CategoryError, match=message):
        categories.load_tree(bad)
