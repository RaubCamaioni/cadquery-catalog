"""Metadata the catalog keeps beside a model's script: one module per kind (tags, categories, later ones),
each owning its table, its form fields and its templates.

The upload, update and edit routes only call `parse_all` / `save_all` (or `apply`), so a new kind is a new
module and a line in KINDS. Every kind is parsed before any is saved: one bad field stores nothing.
"""

from typing import Any, Mapping, Optional, Protocol

from sqlmodel import Session


class MetadataError(ValueError):
    """A metadata field the user sent is invalid; the message is shown to them as is."""


class MetadataKind(Protocol):
    key: str  # also the form field name; "<key>.present" marks an editor that was shown
    editor_template: str
    display_template: str

    def parse(self, form: Mapping[str, list[str]]) -> Optional[Any]:
        """The value from the form, or None when the form did not include this kind's editor."""

    def save(self, session: Session, model_id: int, value: Any) -> None: ...

    def load(self, session: Session, model_ids: list[int]) -> dict[int, Any]:
        """The value for every id in `model_ids` (an empty value for a model with none)."""


def form_lists(form) -> dict[str, list[str]]:
    """Starlette FormData (or any multi-dict) as {name: [values]}, file fields dropped."""
    return {key: [v for v in form.getlist(key) if isinstance(v, str)] for key in form.keys()}


def parse_all(form: Mapping[str, list[str]]) -> dict[str, Any]:
    parsed = {}
    for kind in KINDS:
        value = kind.parse(form)
        if value is not None:
            parsed[kind.key] = value
    return parsed


def save_all(session: Session, model_id: int, parsed: dict[str, Any]) -> None:
    """Stage every parsed kind on the session; the caller commits."""
    for kind in KINDS:
        if kind.key in parsed:
            kind.save(session, model_id, parsed[kind.key])


def apply(session: Session, model_id: int, form: Mapping[str, list[str]]) -> None:
    save_all(session, model_id, parse_all(form))


def load_all(session: Session, model_ids: list[int]) -> dict[int, dict[str, Any]]:
    loaded = {model_id: {} for model_id in model_ids}
    for kind in KINDS:
        for model_id, value in kind.load(session, model_ids).items():
            loaded[model_id][kind.key] = value
    return loaded


from app.metadata.tags import Tags  # noqa: E402  (the kinds import MetadataError from this module)
from app.metadata.categories import Categories  # noqa: E402

KINDS: list[MetadataKind] = [Tags(), Categories()]
