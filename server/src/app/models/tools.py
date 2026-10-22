from fastapi import Depends, HTTPException
from typing import Annotated, Optional, Any
from profanityfilter import ProfanityFilter
import pyparsing as pp
from sqlmodel import (
    Field,
    Session,
    SQLModel,
    create_engine,
    select,
    Relationship,
    JSON,
    Column,
)
import hashlib
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from sqlalchemy import func, inspect, text
import logging
import ast
import black

from app import ENVIRONMENT

logger = logging.getLogger("uvicorn.error")

sqlite_url = f"sqlite:///{ENVIRONMENT.DATABASE}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


def hash_id(id: str) -> int:
    return int(hashlib.sha256(id.encode()).hexdigest(), 16) % 10**8


class User(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    alias: str = Field(default="annonymous")
    # roles live in the database: an admin is made with an UPDATE, never named in code
    admin: bool = Field(default=False)
    banned: bool = Field(default=False)
    banned_until: Optional[datetime] = Field(default=None)  # a ban lifts itself after this (UTC)
    tools: Optional[list["Tool"]] = Relationship(back_populates="user")

    def __init__(self, **data: Any):
        if "id" in data and isinstance(data["id"], str):
            data["id"] = hash_id(data["id"])
        super().__init__(**data)


class Tool(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    name: str
    code: str
    arguments: dict[str, tuple[str, str]] = Field(default={}, sa_column=Column(JSON))
    tags: list[str] = Field(default={}, sa_column=Column(JSON))
    up_votes: list["UpVote"] = Relationship(back_populates="tool")
    down_votes: list["DownVote"] = Relationship(back_populates="tool")
    reports: list["Report"] = Relationship(back_populates="tool")
    usage: int = Field(default=0)
    # from the validation run at upload: the thumbnail (an SVG line drawing) and the measurements
    preview_svg: str = Field(default="")
    meta: dict = Field(default={}, sa_column=Column(JSON))
    public: bool = Field(default=False)
    annonymous: bool = Field(default=True)
    user_id: int = Field(default=None, foreign_key="user.id")
    user: User = Relationship(back_populates="tools")


class UpVote(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    tool_id: int = Field(foreign_key="tool.id")
    tool: Tool = Relationship(back_populates="up_votes")


class DownVote(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    tool_id: int = Field(foreign_key="tool.id")
    tool: Tool = Relationship(back_populates="down_votes")


class Report(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    tool_id: int = Field(foreign_key="tool.id")
    tool: Tool = Relationship(back_populates="reports")
    reason: str


def get_user(session: Session, id: int) -> User:
    statement = select(User).where(User.id == id)
    existing_user = session.exec(statement).first()

    if existing_user:
        return existing_user
    else:
        new_user = User(id=id)
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return new_user


def get_tools_by_index(
    session: Session,
    start: int,
    end: int,
    only_public: bool = True,
) -> list[tuple[int, str]]:
    with session:
        conditions = []
        if only_public:
            conditions = [Tool.public == True]
        statement = select(Tool.id, Tool.name).where(*conditions).offset(start).limit(end - start)
        return session.exec(statement).all()


def get_tools_by_tags(
    session: Session,
    tags: list[str],
    start: int,
    end: int,
    only_public: bool = True,
) -> list[Tool]:
    with session:
        conditions = [Tool.tags.ilike(f"%{tag}%") for tag in tags]
        if only_public:
            conditions.append(Tool.public == True)
        statement = select(Tool.id, Tool.name).where(*conditions).offset(start).limit(end - start)
        return session.exec(statement).all()


@dataclass
class ToolSummary:
    tool: Tool
    up: int
    down: int
    reports: int


@dataclass
class AccountSummary:
    """An account with its tools and the votes/reports totalled over them (admin page)."""

    user: User
    tools: list[ToolSummary]
    up: int
    down: int
    reports: int


def _counts(session: Session, model, column) -> dict[int, int]:
    rows = session.exec(select(column, func.count()).select_from(model).group_by(column)).all()
    return {tool_id: n for tool_id, n in rows}


def get_users_with_tools(session: Session) -> list[AccountSummary]:
    """Every account (oldest first) with its tools and vote/report totals, for the admin page."""
    ups, downs, reports = (_counts(session, M, M.tool_id) for M in (UpVote, DownVote, Report))
    accounts = []
    for user in session.exec(select(User).order_by(User.id)).all():
        tools = [
            ToolSummary(t, ups.get(t.id, 0), downs.get(t.id, 0), reports.get(t.id, 0))
            for t in session.exec(select(Tool).where(Tool.user_id == user.id).order_by(Tool.id)).all()
        ]
        accounts.append(
            AccountSummary(user, tools, sum(t.up for t in tools), sum(t.down for t in tools), sum(t.reports for t in tools))
        )
    return accounts


BAN_PERIODS_MONTHS = (1, 6, 12)


def set_banned(session: Session, user_id: int, months: Optional[int]) -> None:
    """Ban an account for `months` (its tools are unpublished) or lift the ban with None
    (the tools stay private until the user publishes them again)."""
    user = session.get(User, user_id)
    if user is None:
        return
    if months is None:
        user.banned, user.banned_until = False, None
    else:
        user.banned = True
        user.banned_until = datetime.now(timezone.utc) + timedelta(days=30 * months)
        for tool in session.exec(select(Tool).where(Tool.user_id == user_id)).all():
            tool.public = False
    session.commit()


def lift_expired_ban(session: Session, user: User) -> bool:
    """Clear a ban whose period has passed; True when it was lifted."""
    until = user.banned_until
    if until is not None and until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)  # stored values may come back naive
    if user.banned and until is not None and until <= datetime.now(timezone.utc):
        user.banned, user.banned_until = False, None
        session.add(user)
        session.commit()
        return True
    return False


VOTE_MODELS = {"up": UpVote, "down": DownVote}


def user_vote(session: Session, user_id: int, tool_id: int) -> Optional[str]:
    """'up', 'down' or None: the vote this user has on the tool."""
    for direction, model in VOTE_MODELS.items():
        if session.exec(select(model).where(model.user_id == user_id, model.tool_id == tool_id)).first():
            return direction
    return None


def set_vote(session: Session, user_id: int, tool_id: int, direction: str) -> Optional[str]:
    """One vote per user per tool: voting the same way again removes it, the other way switches it.
    Returns the vote left in place."""
    current = user_vote(session, user_id, tool_id)
    for model in VOTE_MODELS.values():
        for vote in session.exec(select(model).where(model.user_id == user_id, model.tool_id == tool_id)).all():
            session.delete(vote)
    result = None
    if current != direction:
        session.add(VOTE_MODELS[direction](user_id=user_id, tool_id=tool_id))
        result = direction
    session.commit()
    return result


def vote_counts(session: Session, tool_id: int) -> tuple[int, int]:
    up = session.exec(select(func.count()).select_from(UpVote).where(UpVote.tool_id == tool_id)).one()
    down = session.exec(select(func.count()).select_from(DownVote).where(DownVote.tool_id == tool_id)).one()
    return int(up), int(down)


def add_report(session: Session, user_id: int, tool_id: int, reason: str) -> None:
    """One report per user per tool; reporting again replaces the reason."""
    report = session.exec(select(Report).where(Report.user_id == user_id, Report.tool_id == tool_id)).first()
    if report is None:
        report = Report(user_id=user_id, tool_id=tool_id, reason=reason)
    report.reason = reason
    session.add(report)
    session.commit()


def has_reported(session: Session, user_id: int, tool_id: int) -> bool:
    return session.exec(select(Report).where(Report.user_id == user_id, Report.tool_id == tool_id)).first() is not None


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.get(User, user_id)


def get_user_tools(session: Session, user: User) -> list[Tool]:
    statement = select(Tool).where(Tool.user_id == user.id)
    result = session.exec(statement).all()
    return list(result)


def add_tool(session: Session, tool: Tool):
    session.add(tool)
    session.commit()


def get_tool(session: Session, id: Optional[int]):
    statement = select(Tool).where(Tool.id == id)
    result = session.exec(statement)
    return result.first()


def del_tool(session: Session, tool: Tool):
    if not tool:
        return False
    session.delete(tool)
    session.commit()
    return True


def get_tool_by_id(session: Session, tool_id: int) -> Tool | None:
    conditions = [Tool.id == tool_id]
    statement = select(Tool).where(*conditions)
    result = session.exec(statement).first()
    return result


# columns added after the first release; create_all never alters existing tables
MIGRATIONS = [
    ("user", "admin", "BOOLEAN NOT NULL DEFAULT 0"),
    ("user", "banned", "BOOLEAN NOT NULL DEFAULT 0"),
    ("user", "banned_until", "DATETIME"),
    ("tool", "preview_svg", "TEXT NOT NULL DEFAULT ''"),
    ("tool", "meta", "JSON"),
]


def migrate(engine_) -> None:
    """Add any missing columns from MIGRATIONS; safe to run on every start."""
    inspector = inspect(engine_)
    for table, column, definition in MIGRATIONS:
        if table in inspector.get_table_names():
            present = {c["name"] for c in inspector.get_columns(table)}
            if column not in present:
                with engine_.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))


def format_stored_tools(engine_) -> int:
    """Bring every stored tool up to the upload standard (black at the page's line length,
    one trailing newline); safe to run on every start. Returns how many tools changed.
    A tool the formatter cannot parse is left as it is and logged.
    """
    changed = 0
    with Session(engine_) as session:
        for tool in session.exec(select(Tool)):
            try:
                formatted = format_source(tool.code)
            except HTTPException as e:
                logger.warning("tool %s (%s) not reformatted: %s", tool.id, tool.name, e.detail)
                continue
            if formatted != tool.code:
                tool.code = formatted
                session.add(tool)
                changed += 1
        session.commit()
    if changed:
        logger.info("reformatted %s stored tool(s) to the upload standard", changed)
    return changed


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
    migrate(engine)
    format_stored_tools(engine)


def get_session():
    with Session(engine) as session:
        yield session


def get_filter():
    pf = ProfanityFilter()
    yield pf


SessionDep = Annotated[Session, Depends(get_session)]
FilterDep = Annotated[ProfanityFilter, Depends(get_filter)]


class FunctionVisitor(ast.NodeVisitor):
    def __init__(self, module: ast.Module):
        self.nodes: list[ast.FunctionDef] = []
        self.visit(module)

    def visit_FunctionDef(self, node):
        self.nodes.append(node)
        self.generic_visit(node)

    def __iter__(self):
        return iter(self.nodes)


def get_tags(tool_source: str) -> list[str]:
    word = pp.Word(pp.alphanums)
    tag = word + pp.Optional(pp.Suppress(pp.Literal(",")))
    comment_line = pp.Suppress(pp.Literal("#")) + pp.OneOrMore(tag)
    try:
        result = comment_line.parseString(tool_source)
        return list(result)
    except pp.ParseException:
        return []


def get_arguments(tool_name: str, tool_source: str) -> dict[str, str]:
    try:
        tree = ast.parse(tool_source)
    except SyntaxError as e:
        detail = f"Python Syntax Error: line {e.lineno}"
        raise HTTPException(status_code=400, detail=detail)

    try:
        entry_node = next(filter(lambda n: n.name == tool_name, FunctionVisitor(tree)))
    except StopIteration:
        detail = "Entrypoint Not Found: entrypoint function matching file name missing"
        raise HTTPException(status_code=400, detail=detail)

    defaults = [None] * len(entry_node.args.args)
    for i, node in enumerate(entry_node.args.defaults[::-1]):
        default = ast.unparse(node)

        if default[0] in ['"', "'"] and len(default) >= 2:
            default = default[1:-1]

        defaults[-(i + 1)] = default

    arguments = {}
    for arg, default in zip(entry_node.args.args, defaults):
        if not arg.annotation:
            detail = "Annotation Error: arguments to entrypoint function must have annotations"
            raise HTTPException(status_code=400, detail=detail)
        annotation = ast.unparse(arg.annotation)
        if annotation == "Path":
            detail = f"Argument Error: '{arg.arg}' is a Path; a model is built from numbers and choices only"
            raise HTTPException(status_code=400, detail=detail)
        arguments[arg.arg] = (annotation, default)

    return arguments


MAX_LINE_LENGTH = 120


def check_line_lengths(tool_source: str) -> None:
    """Uploaded code is shown as-is on the tool page; keep every line within the page's width."""
    for number, line in enumerate(tool_source.splitlines(), 1):
        if len(line) > MAX_LINE_LENGTH:
            detail = f"Line Too Long: line {number} has {len(line)} characters, wrap lines at {MAX_LINE_LENGTH}"
            raise HTTPException(status_code=400, detail=detail)


def format_source(tool_source: str) -> str:
    """Uploads are stored black-formatted at the page's line length and end with a newline,
    so every tool on the site reads the same way whatever editor it came from.
    """
    try:
        formatted = black.format_str(tool_source, mode=black.Mode(line_length=MAX_LINE_LENGTH))
    except black.InvalidInput as e:
        raise HTTPException(status_code=400, detail=f"Python Syntax Error: {e}")
    if not formatted.endswith("\n"):
        formatted += "\n"
    return formatted


def create_tool(user_id: int, tool_name: str, tool_source: str) -> Tool:
    tool_source = tool_source.replace("\r\n", "\n").replace("\r", "\n")
    tool_source = format_source(tool_source)
    # black wraps code but leaves long strings and comments alone, so those still need the author
    check_line_lengths(tool_source)
    tags = get_tags(tool_source.split("\n")[0])
    tags.append(tool_name)
    arguments = get_arguments(tool_name, tool_source)

    return Tool(
        name=tool_name,
        code=tool_source,
        arguments=arguments,
        user_id=user_id,
        tags=tags,
    )
