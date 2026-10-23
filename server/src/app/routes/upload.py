from fastapi import Request, APIRouter, UploadFile, Query
from fastapi.responses import HTMLResponse
from fastapi.exceptions import HTTPException
from app import metadata
from app.models import tools
from app.models.tools import SessionDep, User, FilterDep, get_user, lift_expired_ban
from app.routes.auth import session_user
from pathlib import Path
from app import TEMPLATES, ENVIRONMENT, logger
from app.routes.tools import Tempdir
from app.utility.build_files import MAX_BYTES, checked_meta, read_build_file
from typing import Optional
from urllib.parse import parse_qsl

router = APIRouter()


@router.delete("/manage/model/delete/{id}", response_class=HTMLResponse)
async def tool_delete(
    request: Request,
    id: int,
    session: SessionDep,
):
    user = session_user(request)
    if user is None:
        logger.info("user is not logged in")
        return HTMLResponse(status_code=407)

    tool = tools.get_tool(session, id)
    if tool is None:
        logger.info("unable to find tool")
        return HTMLResponse(status_code=404)

    # the owner, or an admin removing an offending upload
    if user.id != tool.user_id and not user.admin:
        logger.info("tool does not belong to user")
        return HTMLResponse(status_code=404)

    tools.del_tool(session, tool)
    return HTMLResponse(status_code=200)


@router.get("/manage/model/upload", response_class=HTMLResponse)
async def tool_upload_get(request: Request):
    return TEMPLATES.TemplateResponse(
        request,
        "pages/upload.html",
        {
            "header_title": "upload",
            "request": request,
            "root_path": request.scope.get("root_path"),
        },
    )


async def validate_model(tool: tools.Tool, temp_dir: Path) -> dict:
    """Build the model once with its defaults in the sandbox. Returns the export dict (stl, step,
    preview, meta) or raises a 400 with the reason the build failed; an upload that cannot build
    is never stored.
    """
    from app.routes.tools import _coerce, build_failure, build_model

    result = await build_model(tool, _coerce(tool, {}), temp_dir)
    failure = build_failure(result)
    if failure is not None:
        raise HTTPException(status_code=400, detail=f"Model Build Failed: {failure}")
    return result.results


def store_default_build(tool: tools.Tool, build: dict) -> None:
    """Keep the default STL and STEP beside the database and the thumbnail and measurements on the row."""
    target = ENVIRONMENT.MODELS_DIR / str(tool.id)
    target.mkdir(parents=True, exist_ok=True)
    # read again through the same checks: never follow a link or open a FIFO the model left behind
    for key, name in (("stl", "model.stl"), ("step", "model.step")):
        (target / name).write_bytes(read_build_file(build[key], MAX_BYTES[key]))
    try:
        tool.preview_svg = read_build_file(build["preview"], MAX_BYTES["preview"]).decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Model Build Failed: preview.svg is not text")
    tool.meta = checked_meta(build["meta"])


def _uploader(request: Request, session) -> User:
    """The logged-in, unbanned user from the database (the cookie only says who is logged in)."""
    session_account = session_user(request)
    if session_account is None:
        raise HTTPException(status_code=404, detail="Uploading code requires login.")
    user: User = get_user(session, session_account.id)
    lift_expired_ban(session, user)
    if user.banned:
        raise HTTPException(status_code=403, detail="This account is banned.")
    return user


async def _parse_metadata(request: Request) -> dict:
    """Every metadata field in the form, checked before anything else is done: a bad field costs no build."""
    try:
        return metadata.parse_all(metadata.form_lists(await request.form()))
    except metadata.MetadataError as e:
        raise HTTPException(status_code=400, detail=str(e))


async def _read_code(file: Optional[UploadFile], filter) -> Optional[tuple[str, str]]:
    """(name, code) of the uploaded file, or None when the form's file input was left empty."""
    if file is None or not file.filename:
        return None
    code = (await file.read()).decode()
    if not filter.is_clean(code):
        raise HTTPException(status_code=400, detail="Blocked by profanity filter.")
    return Path(file.filename).stem, code


@router.post("/manage/model/upload", response_class=HTMLResponse)
async def model_create(
    request: Request,
    session: SessionDep,
    filter: FilterDep,
    temp_dir: Tempdir,
    file: Optional[UploadFile] = None,
):
    """The dialog's [create]: a new model from its file and its metadata."""
    user = _uploader(request, session)
    parsed = await _parse_metadata(request)
    upload = await _read_code(file, filter)
    if upload is None:
        raise HTTPException(status_code=400, detail="Choose the model's .py file.")
    tool = tools.create_tool(user.id, *upload)
    build = await validate_model(tool, temp_dir)
    session.add(tool)
    session.commit()
    session.refresh(tool)
    store_default_build(tool, build)
    metadata.save_all(session, tool.id, parsed)
    session.commit()
    return HTMLResponse(status_code=200)


@router.post("/manage/model/update/{id}", response_class=HTMLResponse)
async def model_update(
    request: Request,
    id: int,
    session: SessionDep,
    filter: FilterDep,
    temp_dir: Tempdir,
    file: Optional[UploadFile] = None,
):
    """The dialog's [save]: the metadata, and the code too when a file was chosen. The owner may do both; an
    admin may change another user's metadata but never their code."""
    user = _uploader(request, session)
    db_tool: Optional[tools.Tool] = tools.get_tool(session, id)
    if db_tool is None or (db_tool.user_id != user.id and not user.admin):
        raise HTTPException(status_code=404, detail="Model does not belong to you.")
    parsed = await _parse_metadata(request)
    upload = await _read_code(file, filter)
    if upload is not None:
        if db_tool.user_id != user.id:
            raise HTTPException(status_code=404, detail="Model does not belong to you.")
        tool = tools.create_tool(user.id, *upload)
        build = await validate_model(tool, temp_dir)
        db_tool.name = tool.name
        db_tool.code = tool.code
        db_tool.arguments = tool.arguments
        store_default_build(db_tool, build)
    metadata.save_all(session, db_tool.id, parsed)
    session.commit()
    return HTMLResponse(status_code=200)


@router.post("/manage/user/settings", response_class=HTMLResponse)
async def user_settings(
    request: Request,
    session: SessionDep,
):
    if "user" not in request.session:
        raise HTTPException(status_code=404, detail="Requires Login.")
    user: User = User.model_validate_json(request.session["user"])
    user: User = get_user(session, user.id)

    form_data = await request.form()

    if "alias" in form_data:
        user.alias = str(form_data["alias"])

    # update session and database
    request.session["user"] = user.model_dump_json()
    session.commit()

    return HTMLResponse(status_code=200)


@router.post("/manage/model/settings/{id}", response_class=HTMLResponse)
async def tool_set_public(
    request: Request,
    session: SessionDep,
    id: int,
    public: Optional[bool] = None,
    anonymous: Optional[bool] = None,
):
    if "user" not in request.session:
        raise HTTPException(status_code=404, detail="Requires login.")
    user: User = User.model_validate_json(request.session["user"])

    db_tool: Optional[tools.Tool] = tools.get_tool(session, id)

    if db_tool is None:
        raise HTTPException(status_code=404, detail="Tool does not exist.")

    if db_tool.user_id != user.id:
        raise HTTPException(status_code=404, detail="Tool owner does not match user.")

    if public is not None:
        db_tool.public = public

    if anonymous is not None:
        db_tool.annonymous = anonymous

    session.commit()
    return HTMLResponse(status_code=200)
