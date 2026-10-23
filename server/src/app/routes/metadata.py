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
from app.models.tools import SessionDep, get_user
from app.routes.auth import session_user
from app.utility import render

router = APIRouter()


def can_edit(request: Request, session, model: tools.Tool) -> bool:
    account = session_user(request)
    if account is None:
        return False
    user = get_user(session, account.id)  # the admin flag is read from the database, never the cookie
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
    return render.model_meta(request.scope.get("root_path"), model.id, values, can_edit(request, session, model))


@router.get("/model/{id}/metadata", response_class=HTMLResponse)
async def view_metadata(request: Request, id: int, session: SessionDep):
    from app.routes.tools import _require_view

    model = _model(session, id)
    _require_view(request, model)
    return HTMLResponse(display(request, session, model))


@router.get("/manage/model/{id}/metadata/edit", response_class=HTMLResponse)
async def edit_metadata_form(request: Request, id: int, session: SessionDep):
    model = _editable(request, session, id)
    values = metadata.load_all(session, [model.id])[model.id]
    return HTMLResponse(render.model_meta_editors(request.scope.get("root_path"), model.id, values))


@router.post("/manage/model/{id}/metadata", response_class=HTMLResponse)
async def edit_metadata(request: Request, id: int, session: SessionDep):
    model = _editable(request, session, id)
    form = metadata.form_lists(await request.form())
    try:
        parsed = metadata.parse_all(form)
    except metadata.MetadataError as e:
        raise HTTPException(status_code=400, detail=str(e))
    metadata.save_all(session, model.id, parsed)
    session.commit()
    return HTMLResponse(display(request, session, model))


@router.get("/tags/suggest", response_class=HTMLResponse)
async def tag_suggestions(session: SessionDep, q: str = ""):
    """<option>s for the tag editor's datalist: tags in use on public models, most used first."""
    from html import escape

    options = [f'<option value="{escape(tag)}">{escape(tag)} · {count}</option>' for tag, count in suggest(session, q)]
    return HTMLResponse("\n".join(options))
