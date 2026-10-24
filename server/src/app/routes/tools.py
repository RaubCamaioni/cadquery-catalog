from fastapi.responses import (
    Response,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
    FileResponse,
)
from urllib.parse import (
    unquote,
    parse_qs,
    quote_plus,
    urlparse,
    ParseResultBytes,
    urljoin,
    urlencode,
)
from fastapi import FastAPI, HTTPException, Request, APIRouter, Depends, Query
from starlette.datastructures import UploadFile as StarUploadFile
from typing import Literal, get_origin, Annotated, Optional
from contextlib import asynccontextmanager, suppress
from zipfile import ZipFile
from pathlib import Path, PurePosixPath
from io import BytesIO
import asyncio
import hashlib
import secrets
import shutil
import time
import stat
import os

from app.utility import render, serializer, security
from app.utility.podman_runner import PodmanRunner, Outcome, SandboxBusy, SandboxUnavailable
from app.utility.trace import TraceRegistry
from app.utility.annotations import AnnotationError, resolve_annotation
from app.utility.build_files import BuildFileError, checked_build
from app import TEMPLATES, ALLOWED_CHARACTERS, logger, ENVIRONMENT
from app.models import tools as db_tools
from app.routes.auth import User, session_user
from app.routes import metadata as metadata_routes
import json
import re
from pathlib import PosixPath


class PathEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, PosixPath):
            return str(obj)
        return super().default(obj)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # pages are served immediately; tool runs return 503 until the sandbox self-test passes
    runner.start_in_background()
    yield
    delete_tasks = []
    for task in asyncio.all_tasks():
        if "delete" in task.get_name():
            delete_tasks.append(task)
            task.cancel()
    await asyncio.gather(*delete_tasks)
    await runner.stop()


runner = PodmanRunner(ENVIRONMENT.sandbox)
router = APIRouter(lifespan=lifespan)

# execution trace: the tool page registers a random token with its run and streams the run's
# line numbers from /trace/{token} (docs/superpowers/specs/2026-10-19-execution-trace-design.md)
TRACES = TraceRegistry()
TRACE_TOKEN = re.compile(r"[A-Za-z0-9_-]{32}")
TRACE_HEADER = "X-Trace-Token"
TRACE_WAIT_SECONDS = 10.0  # how long a stream waits for its run to be registered
TRACE_POLL_SECONDS = 0.05
TRACE_IDLE_SECONDS = 1.0  # between checks that the stream was not superseded


def _require_view(request: Request, tool) -> None:
    """A private tool is visible to its owner and to admins; everyone else gets a 404."""
    if tool.public:
        return
    user = session_user(request)
    if user is None or (tool.user_id != user.id and not user.admin):
        raise HTTPException(status_code=404, detail="Model Not Found")


async def delete_temp_dir(temp_dir: Path):
    try:
        with suppress(asyncio.CancelledError):
            await asyncio.sleep(60 * 10)
    finally:
        if temp_dir.exists() and temp_dir.is_dir():
            shutil.rmtree(temp_dir)


async def get_temp_dir():
    # a warm sandbox container's directory when one is waiting, else a fresh one
    temp_dir = runner.new_run_dir()
    try:
        yield temp_dir
    finally:
        task = delete_temp_dir(temp_dir)
        asyncio.create_task(task, name=f"delete-{temp_dir}")


Tempdir = Annotated[Path, Depends(get_temp_dir)]


@router.get("/healthz")
async def healthz():
    if runner.available:
        return JSONResponse({"sandbox": "ready"})
    return JSONResponse({"sandbox": "unavailable", "reason": runner.unavailable_reason}, status_code=503)


@router.get("/trace/{token}")
async def trace_stream(token: str):
    if not TRACE_TOKEN.fullmatch(token):
        raise HTTPException(status_code=404, detail="Not Found")

    async def wait_for_channel():
        deadline = time.monotonic() + TRACE_WAIT_SECONDS
        while (channel := TRACES.get(token)) is None and time.monotonic() < deadline:
            await asyncio.sleep(TRACE_POLL_SECONDS)
        return channel

    async def stream():
        channel = await wait_for_channel()
        if channel is not None:
            ticket = channel.attach()
            while True:
                try:
                    line = await asyncio.wait_for(channel.queue.get(), TRACE_IDLE_SECONDS)
                except asyncio.TimeoutError:
                    superseded = channel.ticket != ticket or TRACES.get(token) not in (channel, None)
                    if superseded or channel.closed:  # closed: a later stream found the end marker already taken
                        break
                    continue
                if line is None:
                    break
                yield f"event: line\ndata: {line}\n\n"
        yield "event: end\ndata:\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.api_route("/", methods=["GET", "POST"])
async def read_root(request: Request, session: db_tools.SessionDep, search: str = ""):
    from app.routes.browse import index_page

    return index_page(request, session, None, search)


@router.post("/models", response_class=JSONResponse)
async def get_tools(
    request: Request,
    session: db_tools.SessionDep,
    start: int = Query(0, ge=0),
    end: int = Query(100, ge=0),
):
    if start > end:
        raise HTTPException(status_code=400, detail="Invalid index range")

    body = await request.body()
    search_string = unquote(body.decode())
    query_params = parse_qs(search_string)
    # every typed word must match the model's name or one of its tags
    tags = query_params.get("search", [""])[0].split()
    category = query_params.get("category", [""])[0] or None  # an unknown one matches nothing
    tools = db_tools.search_models(session, tags, start, end, category=category)

    if len(tools) < (end - start):
        end = None

    content = render.list_items(
        request.scope.get("root_path"), tools, end, tags, page=end - start if end else 50, category=category
    )
    return HTMLResponse(content=content)


@router.post("/user/models", response_class=JSONResponse)
async def get_user_tools(request: Request, session: db_tools.SessionDep):
    if "user" not in request.session:
        return HTMLResponse(content="")
    user: User = User.model_validate_json(request.session["user"])
    tools = db_tools.get_user_tools(session, user)
    content = render.list_item_user(request.scope.get("root_path"), tools)
    return HTMLResponse(content=content)


# currently unused
@router.get("/model/{id}/link", response_class=HTMLResponse)
async def tool_link(request: Request, id: int, session: db_tools.SessionDep):
    tool = db_tools.get_tool_by_id(session, id)

    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")

    if not tool.public:
        if "user" not in request.session:
            raise HTTPException(status_code=404, detail="Model Not Found")
        user: User = User.model_validate_json(request.session["user"])

        if tool.user_id != user.id:
            raise HTTPException(status_code=404, detail="Model Not Found")

    form_data = {}
    if len(tool.arguments):
        form_data = await request.form()

    parsed_url: ParseResultBytes = urlparse(str(request.url))
    root_path = request.scope.get("root_path")

    url = urljoin(
        f"{parsed_url.scheme}://{parsed_url.netloc}",
        f"{root_path}/model/{id}",
    )

    query_string = urlencode(form_data)
    content = f"{url}?{query_string}"

    return HTMLResponse(content=content)


@router.get("/model/{id}", response_class=HTMLResponse)
async def entrypoint_page(request: Request, id: int, session: db_tools.SessionDep):
    tool = db_tools.get_tool_by_id(session, id)

    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")

    _require_view(request, tool)

    root_path = request.scope.get("root_path") or ""
    query = dict(request.query_params)
    arguments = tool.arguments

    for name, default in query.items():
        if name not in arguments:
            continue
        t, d = arguments[name]
        arguments[name] = (t, default)

    return TEMPLATES.TemplateResponse(
        request,
        "pages/tool.html",
        {
            "header_title": "CadQuery Catalog",
            "tool": tool.name,
            "tool_id": tool.id,
            "runs": render.format_runs(tool.usage),
            "request": request,
            "root_path": request.scope.get("root_path"),
            "endpoint": f"{request.scope.get('root_path') or ''}/model/{tool.id}",
            "code": tool.code,
            "lines": len(tool.code.splitlines()),  # vim's count: a final newline ends a line, it does not start one
            "form_groups": render.args_to_form(tool.arguments),
            "time": time.time(),
            "votes": _votes_block(request, session, tool.id),
            "author": _author_label(session, tool),
            "model_meta": metadata_routes.display(request, session, tool),
            "meta": tool.meta or {},
            "default_build": (
                render.model_result(
                    root_path,
                    tool.name,
                    f"{root_path}/model/{tool.id}/model.stl",
                    f"{root_path}/model/{tool.id}/model.step",
                    tool.meta,
                )
                if tool.meta
                else ""
            ),
        },
    )


def _author_label(session, tool) -> str:
    """alias#id of the uploader; an anonymous tool shows neither (the id would identify the account)."""
    author = db_tools.get_user_by_id(session, tool.user_id) if tool.user_id is not None else None
    if tool.annonymous or author is None:
        return "anonymous#" + "0" * len(str(tool.user_id or 0))
    return f"{author.alias}#{tool.user_id}"


REPORT_REASON_MAX = 1000


def _votes_block(request: Request, session, tool_id: int, login_needed: Optional[str] = None) -> str:
    """Render the vote/report block for the current viewer."""
    user = session_user(request)
    up, down = db_tools.vote_counts(session, tool_id)
    my_vote = db_tools.user_vote(session, user.id, tool_id) if user else None
    reported = db_tools.has_reported(session, user.id, tool_id) if user else False
    return render.tool_votes(request.scope.get("root_path"), tool_id, up, down, my_vote, reported, login_needed)


@router.post("/model/{id}/vote", response_class=HTMLResponse)
async def vote_tool(request: Request, id: int, direction: str, session: db_tools.SessionDep):
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction must be up or down")
    tool = db_tools.get_tool_by_id(session, id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")
    _require_view(request, tool)
    user = session_user(request)
    if user is None:
        return HTMLResponse(_votes_block(request, session, id, login_needed="vote"))
    db_tools.set_vote(session, user.id, id, direction)
    return HTMLResponse(_votes_block(request, session, id))


@router.post("/model/{id}/report", response_class=HTMLResponse)
async def report_tool(request: Request, id: int, session: db_tools.SessionDep):
    tool = db_tools.get_tool_by_id(session, id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")
    _require_view(request, tool)
    user = session_user(request)
    if user is None:
        return HTMLResponse(_votes_block(request, session, id, login_needed="report"))
    form = await request.form()
    reason = str(form.get("reason", "")).strip()
    if not reason or len(reason) > REPORT_REASON_MAX:
        raise HTTPException(status_code=400, detail=f"A reason of 1 to {REPORT_REASON_MAX} characters is required")
    db_tools.add_report(session, user.id, id, reason)
    return HTMLResponse(_votes_block(request, session, id))


@router.get("/public/model/{id}", response_class=HTMLResponse)
async def public_tool(
    request: Request,
    id: int,
    session: db_tools.SessionDep,
    public: bool = False,
):
    if "user" not in request.session:
        raise HTTPException(status_code=403, detail="Forbidden")

    user: User = User.model_validate_json(request.session.get("user"))
    tool = db_tools.get_tool_by_id(session, id)

    if user.id != tool.user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")

    tool.public = public
    session.commit()

    return HTMLResponse(status_code=200)


UPLOAD_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9._ -]")


def _upload_path(run_dir: Path, key: str, filename: Optional[str]) -> Path:
    """Where an uploaded file is written: its own directory, inputs/<argument>/, under a cleaned name.

    The visitor's name must not reach the run directory itself, where `result.json`, `args.json`,
    the model's file and its exports live, nor leave it. Only the last component survives, reduced to
    plain characters and without a leading dot.
    """
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    name = UPLOAD_NAME_UNSAFE.sub("_", name).lstrip(". ")[:128] or key
    directory = run_dir / "inputs" / key
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    if path.resolve().parent != directory.resolve():
        raise HTTPException(status_code=400, detail="Bad upload filename")
    return path


def _coerce(tool, values: dict, run_dir: Optional[Path] = None) -> dict:
    """Typed keyword arguments for the entrypoint: submitted values, the declared default otherwise.
    A file parameter (Path) becomes the uploaded file saved into the run directory, or None when
    nothing was uploaded: models build a demo in that case, which is also how validation runs.
    """
    kwargs = {}
    for key, (type_name, default) in tool.arguments.items():
        value = values.get(key, default)
        # the stored annotation is mapped to a type through an allow-list, never evaluated: this runs
        # in the web app, outside the sandbox
        try:
            python_type = resolve_annotation(type_name)
        except AnnotationError:
            raise HTTPException(status_code=400, detail=f"Argument Error: '{key}' has an unsupported annotation")
        if python_type is Path:
            upload = value if isinstance(value, StarUploadFile) and value.filename else None
            if upload is None or run_dir is None:
                kwargs[key] = None
            else:
                target = _upload_path(run_dir, key, upload.filename)
                with open(target, "xb") as f:
                    f.write(upload.file.read())
                kwargs[key] = target
        elif get_origin(python_type) is Literal or python_type is str:
            kwargs[key] = str(value)
        else:
            try:
                kwargs[key] = python_type(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Argument Error: {key} must be {type_name}")
    return kwargs


async def build_model(tool, kwargs: dict, temp_dir: Path, on_line=None):
    """Run a model's code in the sandbox with the given arguments; the result is the export dict or an error."""
    if not runner.available:
        raise HTTPException(status_code=503, detail="Sandbox unavailable")
    temp_tool = (temp_dir / tool.name).with_suffix(".py")
    temp_tool.write_text(tool.code, encoding="utf-8")
    with open(temp_dir / "args.json", "w") as f:
        serializer.dump(kwargs, f)
    # !DANGER! user submitted code
    try:
        result = await runner.run(temp_tool, temp_dir, on_line=on_line)
    except SandboxBusy:
        raise HTTPException(status_code=503, detail="Server busy, try again")
    except SandboxUnavailable:
        raise HTTPException(status_code=503, detail="Sandbox unavailable")
    # result.json is written by the run and can name any host path: keep only what the run directory holds
    if result.outcome is Outcome.OK and isinstance(result.results, dict):
        try:
            result.results = checked_build(temp_dir, result.results)
        except BuildFileError as e:
            result.results = f"Export Error: {e}"
    return result


def build_failure(result) -> Optional[str]:
    """Why a build did not produce a model, or None when it did."""
    if result.outcome is not Outcome.OK:
        return result.message + (f"\n{result.stderr_tail}" if result.stderr_tail else "")
    if not isinstance(result.results, dict) or "stl" not in result.results:
        return str(result.results)  # the runtime's own error text (Runtime Error ..., Export Error ...)
    return None


def model_file_urls(root_path: str, result_files: dict) -> tuple[str, str]:
    """Download URLs (under /download/) for the stl and step of a run."""

    def url(path: Path) -> str:
        return (root_path or "") + (Path("/download") / path.relative_to(path.anchor)).as_posix()

    return url(result_files["stl"]), url(result_files["step"])


async def _run_tool(request: Request, id: int, temp_dir: Path, session, channel):
    tool = db_tools.get_tool_by_id(session, id)

    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")

    _require_view(request, tool)

    values = {}
    if len(tool.arguments):
        form = await request.form()
        values = {k: v for k, v in form.items() if k in tool.arguments}
    kwargs = _coerce(tool, values, temp_dir)

    tool.usage = tool.usage + 1
    session.commit()

    return await build_model(tool, kwargs, temp_dir, on_line=channel.put if channel is not None else None)


@router.post("/model/{id}", response_class=HTMLResponse)
async def run_isolated(
    request: Request,
    id: int,
    temp_dir: Tempdir,
    session: db_tools.SessionDep,
) -> str:
    # the page sends its trace token as a header so it can never collide with a tool argument
    token = request.headers.get(TRACE_HEADER, "")
    channel = None
    if TRACE_TOKEN.fullmatch(token):
        TRACES.expire()
        channel = TRACES.register(token)
    try:
        result = await _run_tool(request, id, temp_dir, session, channel)
    finally:
        if channel is not None:
            channel.close()  # every exit, including 404/503, ends the page's trace stream

    htmx = request.headers.get("HX-Request") == "true"
    root_path = request.scope.get("root_path") or ""
    failure = build_failure(result)

    if failure is not None:
        logger.warning(f"model {id} {result.outcome.name}: {failure[:200]}")
        if htmx:
            return HTMLResponse(content=render.render(failure))
        return JSONResponse({"detail": failure}, status_code=422)

    stl_url, step_url = model_file_urls(root_path, result.results)
    if htmx:
        tool = db_tools.get_tool_by_id(session, id)
        return HTMLResponse(
            content=render.model_result(root_path, tool.name, stl_url, step_url, result.results["meta"])
        )
    return json.dumps({"stl": stl_url, "step": step_url, "meta": result.results["meta"]})


@router.get("/model/{id}/preview.svg")
async def model_preview(request: Request, id: int, session: db_tools.SessionDep):
    """The thumbnail drawn at upload (white lines, transparent background)."""
    tool = db_tools.get_tool_by_id(session, id)
    if tool is None or not tool.preview_svg:
        raise HTTPException(status_code=404, detail="No preview")
    _require_view(request, tool)
    # a re-upload replaces the thumbnail, so browsers revalidate: the ETag is the drawing's hash
    etag = hashlib.sha256(tool.preview_svg.encode("utf-8")).hexdigest()[:16]
    if request.headers.get("if-none-match") == f'"{etag}"':
        return Response(status_code=304, headers={"ETag": f'"{etag}"'})
    headers = {"Cache-Control": "no-cache", "ETag": f'"{etag}"'}
    return Response(content=tool.preview_svg, media_type="image/svg+xml", headers=headers)


@router.get("/model/{id}/model.{ext}")
async def model_default_file(request: Request, id: int, ext: Literal["stl", "step"], session: db_tools.SessionDep):
    """The model built with its default parameters, kept from the validation run at upload."""
    tool = db_tools.get_tool_by_id(session, id)
    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")
    _require_view(request, tool)
    path = ENVIRONMENT.MODELS_DIR / str(tool.id) / f"model.{ext}"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="No default build for this model")
    media = "model/stl" if ext == "stl" else "application/step"
    return FileResponse(path, media_type=media, filename=f"{tool.name}.{ext}")


@security.constant_time_with_random_delay(0.2, 1)
@router.get("/download/{file_str:path}", response_class=FileResponse)
async def download_file(file_str: str, preview: bool = False):
    file_path = (Path("/") / Path(file_str)).resolve()
    run_root = ENVIRONMENT.sandbox.run_dir.resolve()

    # only files inside a run directory are served
    if not file_path.is_relative_to(run_root) or file_path == run_root:
        raise HTTPException(status_code=403, detail="Forbidden File Access")

    if not file_path.is_file():
        # run directories are removed ten minutes after the run (and on a restart of the app)
        raise HTTPException(
            status_code=404, detail="This result has expired: files are kept for 10 minutes after a run."
        )

    # a preview is a file the result page embeds (image, audio, video, pdf): real media type, inline
    if preview and file_path.suffix.lower() in render.PREVIEW_SUFFIXES:
        return FileResponse(
            file_path,
            media_type=render.preview_media_type(file_path.name),
            filename=file_path.name,
            content_disposition_type="inline",
        )

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=file_path.name,
    )


@router.get("/terms-of-service", response_class=FileResponse)
async def terms_of_service(request: Request):
    kwargs = {"request": request, "header_title": "CadQuery Catalog"}
    return TEMPLATES.TemplateResponse(request, "pages/terms_of_service.html", kwargs)


@router.get("/privacy-policy", response_class=FileResponse)
async def privacy_policy(request: Request):
    kwargs = {"request": request, "header_title": "CadQuery Catalog"}
    return TEMPLATES.TemplateResponse(request, "pages/privacy_policy.html", kwargs)
