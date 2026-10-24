from fastapi.responses import (
    Response,
    HTMLResponse,
    JSONResponse,
    StreamingResponse,
    FileResponse,
)
from urllib.parse import (
    quote,
    unquote,
    parse_qs,
    quote_plus,
    urlparse,
    ParseResultBytes,
    urljoin,
    urlencode,
)
from fastapi import FastAPI, HTTPException, Request, APIRouter, Query
from starlette.datastructures import UploadFile as StarUploadFile
from typing import Literal, Optional
from contextlib import asynccontextmanager
from zipfile import ZipFile
from io import BytesIO
import asyncio
import hashlib
import time

from sandboxcore.host import (
    InputFile,
    Job,
    JobError,
    Outcome,
    OutputFile,
    Sandbox,
    SandboxBusy,
    SandboxUnavailable,
    Signature,
    SignatureError,
    Source,
    SourceError,
)
from app.utility.trace_stream import TraceRegistry
from app.utility import render
from app.utility.build_files import BuildFileError, checked_build
from app import TEMPLATES, logger, ENVIRONMENT
from app.models import tools as db_tools
from app.routes.auth import User, session_user
from app.routes import metadata as metadata_routes
import json
import re


@asynccontextmanager
async def lifespan(app: FastAPI):
    # pages are served immediately; tool runs return 503 until the sandbox self-test passes
    sandbox.start_in_background()
    yield
    await sandbox.stop()  # also removes every kept run directory


sandbox = Sandbox(ENVIRONMENT.sandbox)
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


@router.get("/healthz")
async def healthz():
    if sandbox.available:
        return JSONResponse({"sandbox": "ready"})
    return JSONResponse({"sandbox": "unavailable", "reason": sandbox.unavailable_reason}, status_code=503)


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


async def build_model(tool, values: dict, on_line=None):
    """Build a model's code in the sandbox from submitted values ({} builds it with its defaults).
    The result's value is the checked export dict, or the error text."""
    if not sandbox.available:
        raise HTTPException(status_code=503, detail="Sandbox unavailable")
    # the stored signature is checked again and every value converted through it, never evaluated:
    # this runs in the web app, outside the sandbox. A file parameter without an upload is left out,
    # so the model's own `= None` default builds its demo
    try:
        signature = Signature.from_arguments("python", tool.name, tool.arguments)
        arguments, files = signature.bind(values)
        job = Job(Source("python", tool.name, tool.code), arguments, files)
    except (SignatureError, SourceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    # !DANGER! user submitted code
    try:
        result = await sandbox.run(job, on_line=on_line)
    except (JobError, SourceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except SandboxBusy:
        raise HTTPException(status_code=503, detail="Server busy, try again")
    except SandboxUnavailable:
        raise HTTPException(status_code=503, detail="Sandbox unavailable")
    # the core vetted every file; keep only the export's fixed names and the measurements' shape
    if result.outcome is Outcome.OK and isinstance(result.value, dict):
        try:
            result.value = checked_build(result.value)
        except BuildFileError as e:
            result.value = f"Export Error: {e}"
    return result


def build_failure(result) -> Optional[str]:
    """Why a build did not produce a model, or None when it did."""
    if result.outcome is not Outcome.OK:
        return result.message + (f"\n{result.stderr_tail}" if result.stderr_tail else "")
    if not isinstance(result.value, dict) or "stl" not in result.value:
        return str(result.value)  # the runtime's own error text (Runtime Error ..., Export Error ...)
    return None


def download_url(out: OutputFile, root_path: str = "") -> str:
    """Where a file of a run is downloaded: /download/<run>/<name inside the run directory>."""
    return f"{root_path or ''}/download/{out.run}/{quote(out.name)}"


def model_file_urls(root_path: str, build: dict) -> tuple[str, str]:
    """Download URLs for the stl and step of a run."""
    return download_url(build["stl"], root_path), download_url(build["step"], root_path)


async def _form_values(request: Request, tool) -> dict:
    """The submitted values for the model's arguments: strings, and uploads as InputFile (an empty file
    input is no upload). Stray fields are ignored."""
    values = {}
    if len(tool.arguments):
        form = await request.form()
        for key, value in form.items():
            if key not in tool.arguments:
                continue
            if isinstance(value, StarUploadFile):
                if value.filename:
                    values[key] = InputFile(value.filename, await value.read())
            else:
                values[key] = value
    return values


async def _run_tool(request: Request, id: int, session, channel):
    tool = db_tools.get_tool_by_id(session, id)

    if tool is None:
        raise HTTPException(status_code=404, detail="Model Not Found")

    _require_view(request, tool)

    values = await _form_values(request, tool)

    tool.usage = tool.usage + 1
    session.commit()

    return await build_model(tool, values, on_line=channel.put if channel is not None else None)


@router.post("/model/{id}", response_class=HTMLResponse)
async def run_isolated(
    request: Request,
    id: int,
    session: db_tools.SessionDep,
) -> str:
    # the page sends its trace token as a header so it can never collide with a tool argument
    token = request.headers.get(TRACE_HEADER, "")
    channel = None
    if TRACE_TOKEN.fullmatch(token):
        TRACES.expire()
        channel = TRACES.register(token)
    try:
        result = await _run_tool(request, id, session, channel)
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

    stl_url, step_url = model_file_urls(root_path, result.value)
    if htmx:
        tool = db_tools.get_tool_by_id(session, id)
        return HTMLResponse(
            content=render.model_result(root_path, tool.name, stl_url, step_url, result.value["meta"])
        )
    return json.dumps({"stl": stl_url, "step": step_url, "meta": result.value["meta"]})


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


@router.get("/download/{run}/{name:path}", response_class=FileResponse)
async def download_file(run: str, name: str, preview: bool = False):
    # only a file of a run the sandbox still keeps, checked again (no symlinks, nothing outside the run)
    out = sandbox.output(run, name)
    if out is None:
        # run directories are removed ten minutes after the run (and on a restart of the app)
        raise HTTPException(
            status_code=404, detail="This result has expired: files are kept for 10 minutes after a run."
        )

    # a preview is a file the result page embeds (image, audio, video, pdf): real media type, inline
    if preview and out.path.suffix.lower() in render.PREVIEW_SUFFIXES:
        return FileResponse(
            out.path,
            media_type=render.preview_media_type(out.filename),
            filename=out.filename,
            content_disposition_type="inline",
        )

    return FileResponse(
        out.path,
        media_type="application/octet-stream",
        filename=out.filename,
    )


@router.get("/terms-of-service", response_class=FileResponse)
async def terms_of_service(request: Request):
    kwargs = {"request": request, "header_title": "CadQuery Catalog"}
    return TEMPLATES.TemplateResponse(request, "pages/terms_of_service.html", kwargs)


@router.get("/privacy-policy", response_class=FileResponse)
async def privacy_policy(request: Request):
    kwargs = {"request": request, "header_title": "CadQuery Catalog"}
    return TEMPLATES.TemplateResponse(request, "pages/privacy_policy.html", kwargs)
