"""Categories: up to three leaf paths from categories.yaml, the first being the model's primary.

Only paths still in the tree count ("effective" categories); a model with none, or whose paths the tree has
since dropped, belongs to Miscellaneous, so it never disappears from browsing.
"""

from typing import Mapping, Optional

from sqlalchemy import delete, exists, or_
from sqlmodel import Field, Session, SQLModel, select

from app import TEMPLATES, categories

MAX_CATEGORIES = 3

# the editor and display partials label paths and list the choices from the tree
TEMPLATES.env.globals.update(category_label=categories.label, category_leaves=categories.leaves)


class ModelCategory(SQLModel, table=True):
    model_id: int = Field(foreign_key="tool.id", primary_key=True)
    path: str = Field(primary_key=True, index=True)
    position: int = Field(default=0)


def effective(paths: list[str]) -> list[str]:
    live = [path for path in paths if categories.is_leaf(path)]
    return live or [categories.MISC]


def model_ids_in(paths: list[str]):
    """A subquery of the model ids filed under any of `paths` by effective category."""
    from app.models.tools import Tool

    live = [path for path, _ in categories.leaves()]
    filed = select(ModelCategory.model_id).where(ModelCategory.path.in_([p for p in paths if p in live]))
    conditions = [Tool.id.in_(filed)]
    if categories.MISC in paths:
        # misc also holds every model without a live non-misc category
        real = [p for p in live if p != categories.MISC]
        conditions.append(~exists().where(ModelCategory.model_id == Tool.id, ModelCategory.path.in_(real)))
    return select(Tool.id).where(or_(*conditions))


class Categories:
    key = "categories"
    editor_template = "components/meta_categories_editor.html"
    display_template = "components/meta_categories_display.html"

    def parse(self, form: Mapping[str, list[str]]) -> Optional[list[str]]:
        from app.metadata import MetadataError

        if f"{self.key}.present" not in form:
            return None
        paths = [value.strip() for value in form.get(self.key, []) if value.strip()]
        for path in paths:
            if not categories.is_leaf(path):
                valid = ", ".join(p for p, _ in categories.leaves())
                raise MetadataError(f"unknown category {path!r}; choose from: {valid}")
        if len(set(paths)) != len(paths):
            raise MetadataError("a category is listed twice (duplicate)")
        if len(paths) > MAX_CATEGORIES:
            raise MetadataError(f"at most {MAX_CATEGORIES} categories, got {len(paths)}")
        if categories.MISC in paths and len(paths) > 1:
            raise MetadataError("misc cannot be combined with other categories")
        return paths

    def delete(self, session: Session, model_id: int) -> None:
        session.exec(delete(ModelCategory).where(ModelCategory.model_id == model_id))

    def save(self, session: Session, model_id: int, value: list[str]) -> None:
        self.delete(session, model_id)
        for position, path in enumerate(value):
            session.add(ModelCategory(model_id=model_id, path=path, position=position))

    def load(self, session: Session, model_ids: list[int]) -> dict[int, list[str]]:
        stored: dict[int, list[str]] = {model_id: [] for model_id in model_ids}
        if model_ids:
            rows = session.exec(
                select(ModelCategory).where(ModelCategory.model_id.in_(model_ids)).order_by(ModelCategory.position)
            ).all()
            for row in rows:
                stored[row.model_id].append(row.path)
        return {model_id: effective(paths) for model_id, paths in stored.items()}
