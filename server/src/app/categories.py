"""The curated category tree from categories.yaml: two levels, plus Miscellaneous, which has no subcategories.

A model is filed under leaf paths: "<category>/<subcategory>", or "misc". The tree is checked when it loads;
a malformed file raises CategoryError at import, so the app does not start with a broken tree.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import re

import yaml

MISC = "misc"
SLUG = re.compile(r"^[a-z][a-z0-9-]*$")


class CategoryError(ValueError):
    pass


@dataclass(frozen=True)
class Category:
    slug: str
    name: str
    description: str
    subcategories: tuple["Category", ...]
    path: str


def _entry(raw, parent: Optional[str]) -> Category:
    if not isinstance(raw, dict):
        raise CategoryError(f"every category must be a mapping, got {raw!r}")
    slug = raw.get("slug")
    if not isinstance(slug, str) or not SLUG.match(slug):
        raise CategoryError(f"slug {slug!r} must match {SLUG.pattern}")
    path = f"{parent}/{slug}" if parent else slug
    for field in ("name", "description"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise CategoryError(f"{path}: {field} is required")
    subs = raw.get("subcategories") or []
    if parent and subs:
        raise CategoryError(f"{path}: subcategories cannot nest")
    if not isinstance(subs, list):
        raise CategoryError(f"{path}: subcategories must be a list")
    children = tuple(_entry(sub, slug) for sub in subs)
    _unique([c.slug for c in children], path)
    return Category(slug, raw["name"].strip(), raw["description"].strip(), children, path)


def _unique(slugs: list[str], where: str) -> None:
    seen = set()
    for slug in slugs:
        if slug in seen:
            raise CategoryError(f"duplicate slug {slug!r} in {where}")
        seen.add(slug)


def load_tree(text: str) -> tuple[Category, ...]:
    raw = yaml.safe_load(text)
    if not isinstance(raw, list):
        raise CategoryError("the category file must be a list of categories")
    tree = tuple(_entry(entry, None) for entry in raw)
    _unique([c.slug for c in tree], "the top level")
    for category in tree:
        if category.slug == MISC and category.subcategories:
            raise CategoryError("misc is a leaf: it cannot have subcategories")
        if category.slug != MISC and not category.subcategories:
            raise CategoryError(f"{category.slug}: needs at least one of its subcategories (only misc has none)")
    if MISC not in {c.slug for c in tree}:
        raise CategoryError("the tree must end with a misc category for models that fit nowhere else")
    return tree


TREE = load_tree((Path(__file__).parent / "categories.yaml").read_text(encoding="utf-8"))


def find(path: str) -> Optional[Category]:
    """The category (top-level slug) or subcategory (leaf path) at `path`, or None."""
    top, _, sub = path.partition("/")
    for category in TREE:
        if category.slug == top:
            if not sub:
                return category
            return next((c for c in category.subcategories if c.slug == sub), None)
    return None


def is_leaf(path: str) -> bool:
    found = find(path)
    return found is not None and not found.subcategories


def leaves() -> list[tuple[str, str]]:
    """Every path a model can be filed under with its label, in file order."""
    return [(path, label(path)) for c in TREE for path in paths_under(c.slug)]


def label(path: str) -> str:
    """ "Home › Kitchen" for a leaf, "Home" for a category; the path itself if the tree no longer has it."""
    found = find(path)
    if found is None:
        return path
    if "/" not in path:
        return found.name
    return f"{find(path.partition('/')[0]).name} › {found.name}"


def paths_under(slug: str) -> list[str]:
    """The leaf paths under a top-level category (misc is its own leaf); [] for an unknown slug."""
    category = find(slug)
    if category is None or "/" in slug:
        return []
    return [s.path for s in category.subcategories] or [category.path]
