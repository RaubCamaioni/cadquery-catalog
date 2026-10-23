import pyparsing as pp
from typing import Any, get_args
from html import escape
import json
import mimetypes
from pathlib import Path, PosixPath
from jinja2 import Template
from app import TEMPLATES, logger
from typing import Literal, Optional  # required for form type
from nh3 import clean as sanitize_html
from app.models.tools import Tool


def parser_literal(input: str):
    LITERAL = pp.Suppress(pp.Literal("Literal"))
    OPEN_BRACKET = pp.Suppress(pp.Literal("["))
    CLOSE_BRACKET = pp.Suppress(pp.Literal("]"))
    string_type = pp.Word(pp.alphanums + "_", pp.alphanums + "_.")
    num_type = pp.Combine(pp.Optional(".") + pp.Word(pp.nums) + pp.Optional("." + pp.Word(pp.nums)))
    empty_quote = string_type | num_type
    single = pp.Suppress("'")
    doube = pp.Suppress('"')
    double_quote = pp.Group(doube + empty_quote + doube).addParseAction(lambda t: "".join(t[0]))
    single_quote = pp.Group(single + empty_quote + single).addParseAction(lambda t: "".join(t[0]))
    field = double_quote | single_quote | num_type
    literal_values = pp.ZeroOrMore(field + pp.Suppress(pp.Optional(",")))
    literal_expr = LITERAL + OPEN_BRACKET + literal_values + CLOSE_BRACKET
    return literal_expr.parseString(input)


def literal_to_label(name: str, type: str, default: str, glyph: str = ""):
    default = sanitize_html(default) or ""
    values = parser_literal(type)
    options = [{"value": v, "label": v} for v in values]

    template: Template = TEMPLATES.get_template("components/form_literal.html")
    form = template.render(
        {
            "name": name,
            "options": options,
            "py_type": "Literal",
            "glyph": glyph,
        },
    )

    return form


def type_to_label(name: str, type: str, default: str, glyph: str = ""):
    default = sanitize_html(default) or ""

    template: Template = TEMPLATES.get_template("components/form_type.html")
    form = template.render(
        {
            "name": name,
            "type": TYPE_MAP.get(type, "text"),
            "default": default,
            "py_type": type,
            "glyph": glyph,
        },
    )

    return form


TYPE_MAP = {
    "str": "text",
    "int": "number",
    "float": "number",
    "Path": "file",
}

TYPE_TO_LABEL = {
    "str": type_to_label,
    "int": type_to_label,
    "float": type_to_label,
    "Path": type_to_label,
    "Literal": literal_to_label,
}


def form_group(name: str, type: str, default: str, glyph: str = ""):
    default = default or ""

    if "Literal" in type:
        return TYPE_TO_LABEL["Literal"](name, type, default, glyph)

    if type in TYPE_TO_LABEL:
        return TYPE_TO_LABEL[type](name, type, default, glyph)

    return type_to_label(name, "str", "invalid type", glyph)


def args_to_form(arguments: dict[str, tuple[str, str]]):
    # rendered as a tree under the function name: tee glyphs, corner on the last argument
    items = []
    last = len(arguments) - 1
    for i, (name, (type, default)) in enumerate(arguments.items()):
        glyph = "└── " if i == last else "├── "
        items.append(form_group(name, type, default, glyph))

    return "\n".join(items)


def list_items(
    base_url: str,
    tools: list[tuple[str, str]],
    end: Optional[int] = None,
    tags: Optional[list[str]] = None,
    page: int = 50,
    category: Optional[str] = None,
):
    """Render the ls-style tool list; `end` (if any) is where the next page of `page` tools starts; the next
    page's loader carries the search words and the category."""
    tags = tags or []

    htmlx = []
    template: Template = TEMPLATES.get_template("components/index_tool_item.html")
    for id, name in tools:
        form = template.render(
            {
                "name": name,
                "id": id,
                "base_url": base_url,
            },
        )
        htmlx.append(form)

    if end is not None:
        template: Template = TEMPLATES.get_template("components/tool_scroll_loader.html")
        form = template.render(
            {
                "start": end,
                "end": end + page,
                "tags": " ".join(tags),
                "category": category,
                "root_path": base_url or "",  # fragments rendered outside a request must be told the prefix
            },
        )
        htmlx.append(form)

    return "".join(htmlx)


def format_runs(count: int) -> str:
    """A run count in at most four characters: 9999, 10K, 999K, 1.2M, 12M, 999M, 1.2B."""
    count = max(0, int(count))
    for limit, unit in ((1_000_000_000, "B"), (1_000_000, "M")):
        if count >= 10 * limit:
            return f"{count // limit}{unit}"
        if count >= limit:
            return f"{int(count / limit * 10) / 10:.1f}{unit}"  # floored, so 9 999 999 stays 9.9M
    if count >= 10_000:
        return f"{count // 1_000}K"
    return str(count)


def tool_votes(root_path, tool_id, up, down, my_vote=None, reported=False, login_needed=None) -> str:
    """The [up N] [down N] [report] block of a tool page (components/tool_votes.html)."""
    template: Template = TEMPLATES.get_template("components/tool_votes.html")
    return template.render(
        root_path=root_path or "",
        tool_id=tool_id,
        up=up,
        down=down,
        my_vote=my_vote,
        reported=reported,
        login_needed=login_needed,
    )


def model_meta(root_path: str, model_id: int, values: dict) -> str:
    """A model's metadata as each kind's display partial."""
    from app import metadata

    return TEMPLATES.get_template("components/model_meta.html").render(
        root_path=root_path or "", model_id=model_id, kinds=metadata.KINDS, **values
    )


def model_dialog(root_path: str, model_id: Optional[int], name: Optional[str], values: dict) -> str:
    """The profile's create/edit dialog: the file and every kind's editor, filled with `values` when editing."""
    from app import metadata

    return TEMPLATES.get_template("components/model_dialog.html").render(
        root_path=root_path or "", model_id=model_id, name=name, kinds=metadata.KINDS, **values
    )


def list_item_user(root_path: str, tools: list[Tool], meta: Optional[dict[int, dict]] = None):
    template: Template = TEMPLATES.get_template("components/update_tool_item.html")
    # the rows are cells of one grid (`ls -l | column -t`): the header row aligns with them
    htmlx = [
        TEMPLATES.get_template("components/update_tool_header.html").render(),
        TEMPLATES.get_template("components/upload_tool_item.html").render(root_path=root_path or ""),
    ]

    for tool in tools:
        htmlx.append(
            template.render(
                root_path=root_path,
                id=tool.id,
                name=tool.name,
                public="checked" if tool.public else "",
                anonymous="checked" if tool.annonymous else "",
                runs=format_runs(tool.usage),
                categories=(meta or {}).get(tool.id, {}).get("categories", ["misc"]),
            )
        )

    return "".join(htmlx)


# --- result display -------------------------------------------------------------------------
# A tool's return value is shown the way a person wants to read and reuse it, not as a Python
# repr: strings raw (no quotes, line breaks kept), dicts as key/value rows, lists as bullet
# rows, files as download links with the file embedded when the browser can show it (images,
# audio, video, PDF). Every scalar has a [copy] bracket and the whole result a [copy all].

PREVIEW_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif", ".ico"}
PREVIEW_AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac", ".aac", ".opus"}
PREVIEW_VIDEO_SUFFIXES = {".mp4", ".webm", ".ogv"}
PREVIEW_DOCUMENT_SUFFIXES = {".pdf"}
PREVIEW_SUFFIXES = PREVIEW_IMAGE_SUFFIXES | PREVIEW_AUDIO_SUFFIXES | PREVIEW_VIDEO_SUFFIXES | PREVIEW_DOCUMENT_SUFFIXES
# media types the stdlib does not know (or knows wrongly) for the previewed suffixes
PREVIEW_MEDIA_TYPES = {
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".m4a": "audio/mp4",
    ".flac": "audio/flac",
    ".opus": "audio/ogg",
    ".oga": "audio/ogg",
    ".ogv": "video/ogg",
    ".webm": "video/webm",
}


def preview_media_type(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return PREVIEW_MEDIA_TYPES.get(suffix) or mimetypes.guess_type(name)[0] or "application/octet-stream"


def _copy_button(text: str, label: str = "[copy]") -> str:
    return f'<button type="button" class="copy" data-copy="{escape(text, quote=True)}">{label}</button>'


def _download_link(path: Path, root: str) -> str:
    href = root + (Path("/download") / path.relative_to(path.anchor)).as_posix()
    link = f'<a href="{href}" download="{escape(path.name, quote=True)}">{escape(path.name)}</a>'
    suffix = path.suffix.lower()
    if suffix == ".stl":
        embed = f'<stl-viewer url="{href}"></stl-viewer>'
    elif suffix in PREVIEW_IMAGE_SUFFIXES:
        embed = f'<img class="preview" src="{href}?preview=1" alt="{escape(path.name, quote=True)}" loading="lazy">'
    elif suffix in PREVIEW_AUDIO_SUFFIXES:
        embed = f'<audio class="preview" controls preload="metadata" src="{href}?preview=1"></audio>'
    elif suffix in PREVIEW_VIDEO_SUFFIXES:
        embed = f'<video class="preview" controls preload="metadata" src="{href}?preview=1"></video>'
    elif suffix in PREVIEW_DOCUMENT_SUFFIXES:
        embed = f'<object class="preview document" data="{href}?preview=1" type="application/pdf"></object>'
    else:
        embed = ""
    return f'<span class="file">{link}</span>{embed}'


def _scalar(value: Any, root: str = "") -> tuple[str, str]:
    """(html, raw text to copy) for a leaf value."""
    if isinstance(value, bool) or value is None:
        text = {True: "True", False: "False", None: "None"}[value]
        return f'<span class="val lit">{text}</span>', text
    if isinstance(value, (int, float)):
        text = repr(value)
        return f'<span class="val num">{escape(text)}</span>', text
    if isinstance(value, (Path, PosixPath)):
        return f'<span class="val">{_download_link(value, root)}</span>', str(value)
    text = str(value)
    return f'<span class="val str">{escape(text)}</span>', text


CONTAINERS = (dict, list, tuple, set, frozenset)
SEQUENCES = (list, tuple, set, frozenset)


def _node(value: Any, root: str = "") -> str:
    """HTML for any value: a dict as key/value rows, a list as bullet rows, a leaf with its
    [copy] bracket. A list is copied whole (one item per line), never item by item.
    """
    if isinstance(value, dict):
        if not value:
            return '<span class="val lit">{}</span>'
        rows = []
        for key, item in value.items():
            label = f'<span class="key">{escape(str(key))}:</span>'
            if isinstance(item, CONTAINERS) and item:
                copy = _copy_button(_plain_text(item)) if isinstance(item, SEQUENCES) else ""
                rows.append(f'<div class="kv">{label}<span class="cell">{copy}</span></div>')
                rows.append(f'<div class="nest">{_node(item, root)}</div>')
            else:
                html, raw = _scalar(item, root) if not isinstance(item, CONTAINERS) else (_node(item, root), "")
                copy = _copy_button(raw) if raw else ""
                # the bracket follows its value inside one cell, so it is never far from what it copies
                rows.append(f'<div class="kv">{label}<span class="cell">{html}{copy}</span></div>')
        return f'<div class="kv-table">{"".join(rows)}</div>'
    if isinstance(value, SEQUENCES):
        if not value:
            return '<span class="val lit">[]</span>'
        rows = []
        for item in value:
            if isinstance(item, CONTAINERS) and item:
                rows.append(
                    f'<div class="item"><span class="bullet">-</span><div class="nest">{_node(item, root)}</div></div>'
                )
            else:
                html = _scalar(item, root)[0] if not isinstance(item, CONTAINERS) else _node(item, root)
                rows.append(f'<div class="item"><span class="bullet">-</span>{html}</div>')
        return f'<div class="items">{"".join(rows)}</div>'
    html, raw = _scalar(value, root)
    return f'<div class="item">{html}{_copy_button(raw)}</div>'


def _plain_text(value: Any) -> str:
    """What a whole-value [copy] puts on the clipboard: a string as it is, a list of plain
    values one per line, anything else as JSON.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, SEQUENCES) and not any(isinstance(item, CONTAINERS) for item in value):
        return "\n".join(_scalar(item)[1] for item in value)

    def default(obj):
        if isinstance(obj, (Path, PosixPath)):
            return str(obj)
        if isinstance(obj, (set, frozenset)):
            return sorted(obj, key=str)
        return str(obj)

    return json.dumps(value, indent=2, ensure_ascii=False, default=default)


ALLOWED_TAGS = {"div", "span", "pre", "a", "img", "audio", "video", "object", "button", "stl-viewer", "br"}
ALLOWED_ATTRIBUTES = {
    "*": {"class", "title"},
    "a": {"href", "download"},
    "img": {"src", "alt", "loading"},
    "audio": {"src", "controls", "preload"},
    "video": {"src", "controls", "preload"},
    "object": {"data", "type"},
    "button": {"type", "data-copy"},
    "stl-viewer": {"url"},
}


def model_result(root_path: str, name: str, stl_url: str, step_url: str, meta: dict) -> str:
    """The viewer, measurements and download links for a built model (components/model_result.html)."""
    template: Template = TEMPLATES.get_template("components/model_result.html")
    return template.render(root_path=root_path or "", name=name, stl_url=stl_url, step_url=step_url, meta=meta)


def render(results: Any, root_path: str = "") -> str:
    """The result panel; `root_path` is the prefix the app is mounted at (for file links)."""
    body = _node(results, root_path or "")
    # [copy all] only for a container with content: a single value already has its own [copy]
    tools = ""
    if isinstance(results, (dict, list, tuple, set, frozenset)) and results:
        tools = f'<div class="result-tools">{_copy_button(_plain_text(results), "[copy all]")}</div>'
    html = f'<div class="result">{tools}{body}</div>'
    return sanitize_html(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https"},
    )
