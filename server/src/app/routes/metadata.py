"""Editing a model's metadata (tags, categories, later kinds) and suggesting tags already in use.

Only the model's owner or an admin may edit; anyone else gets a 404, as for code updates. The routes go
through the metadata registry, so a new kind needs no change here.
"""

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse

from app import metadata
from app.metadata.tags import suggest
from app.models import tools
from app.models.tools import SessionDep, get_user, lift_expired_ban
from app.routes.auth import session_user
from app.utility import render

router = APIRouter()


def can_edit(request: Request, session, model: tools.Tool) -> bool:
    account = session_user(request)
    if account is None:
        return False
    user = get_user(session, account.id)  # admin and banned are read from the database, never the cookie
    lift_expired_ban(session, user)
    if user.banned:
        return False
    return model.user_id == user.id or user.admin


def _model(session, id: int) -> tools.Tool:
    model: Optional[tools.Tool] = tools.get_tool(session, id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model Not Found")
    return model


def _editable(request: Request, session, id: int) -> tools.Tool:
    model = _model(session, id)
    if not can_edit(request, session, model):
        raise HTTPException(status_code=404, detail="Model Not Found")
    return model


def display(request: Request, session, model: tools.Tool) -> str:
    values = metadata.load_all(session, [model.id])[model.id]
    return render.model_meta(request.scope.get("root_path"), model.id, values)


@router.get("/manage/model/create", response_class=HTMLResponse)
async def create_dialog(request: Request, session: SessionDep):
    """The profile's [create]: the empty dialog."""
    if session_user(request) is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return HTMLResponse(render.model_dialog(request.scope.get("root_path"), None, None, {}))


@router.get("/manage/model/{id}/edit", response_class=HTMLResponse)
async def edit_dialog(request: Request, id: int, session: SessionDep):
    """A row's [edit]: the dialog filled with the model's metadata (owner or admin)."""
    model = _editable(request, session, id)
    values = metadata.load_all(session, [model.id])[model.id]
    return HTMLResponse(render.model_dialog(request.scope.get("root_path"), model.id, model.name, values))


@router.get("/tags/suggest")
async def tag_suggestions(session: SessionDep, q: str = ""):
    """The tag editor's dropdown: tags in use on public models that start with `q`, most used first."""
    return [{"tag": tag, "count": count} for tag, count in suggest(session, q)]
