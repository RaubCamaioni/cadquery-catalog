"""Description: a few sentences of plain text about a model, shown on its page under the title. Line breaks are
kept; nothing is rendered as HTML or markdown."""

from typing import Mapping, Optional

from sqlalchemy import delete
from sqlmodel import Field, Session, SQLModel, select

MAX_LENGTH = 1000


class ModelDescription(SQLModel, table=True):
    model_id: int = Field(foreign_key="tool.id", primary_key=True)
    text: str


class Description:
    key = "description"
    editor_template = "components/meta_description_editor.html"
    display_template = "components/meta_description_display.html"

    def parse(self, form: Mapping[str, list[str]]) -> Optional[str]:
        from app.metadata import MetadataError
        from app.metadata.tags import _profanity

        if f"{self.key}.present" not in form:
            return None
        text = "\n".join(form.get(self.key, [])).replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(text) > MAX_LENGTH:
            raise MetadataError(f"the description is {len(text)} characters; at most {MAX_LENGTH}")
        if text and not _profanity().is_clean(text):
            raise MetadataError("the description is blocked by the profanity filter")
        return text

    def delete(self, session: Session, model_id: int) -> None:
        session.exec(delete(ModelDescription).where(ModelDescription.model_id == model_id))

    def save(self, session: Session, model_id: int, value: str) -> None:
        self.delete(session, model_id)
        if value:
            session.add(ModelDescription(model_id=model_id, text=value))

    def load(self, session: Session, model_ids: list[int]) -> dict[int, str]:
        loaded = {model_id: "" for model_id in model_ids}
        if model_ids:
            for row in session.exec(select(ModelDescription).where(ModelDescription.model_id.in_(model_ids))).all():
                loaded[row.model_id] = row.text
        return loaded
