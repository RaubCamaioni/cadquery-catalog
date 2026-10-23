from fastapi.templating import Jinja2Templates
from pathlib import Path
import string
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from app.utility.sandbox_config import SandboxConfig


REQUIRED_ENVIRONMENT = ("SESSION_KEY", "DATABASE")


@dataclass
class _ENVIRONMENT:
    SESSION_KEY: str = os.environ.get("SESSION_KEY")
    DATABASE: str = os.environ.get("DATABASE")
    # GitHub login is optional: without the keys the site runs with login disabled
    GITHUB_CLIENT_ID: Optional[str] = os.environ.get("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: Optional[str] = os.environ.get("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: str = os.environ.get("GITHUB_REDIRECT_URI", "https://pywebtools.com/auth/github")
    # the GitHub account that owns the tools uploaded under the original (Google) account
    OWNER_GITHUB_LOGIN: str = os.environ.get("OWNER_GITHUB_LOGIN", "RaubCamaioni")
    # the URL prefix the app is served under, e.g. "/models" behind a reverse proxy; "" at the root
    ROOT_PATH: str = os.environ.get("ROOT_PATH", "").rstrip("/")
    # the default STL and STEP of every model (from its validation run) live here, beside the database
    MODELS_DIR: Path = Path(os.environ.get("MODELS_DIR") or (Path(os.environ.get("DATABASE") or "/data/db").parent / "models"))
    # SANDBOX_* variables all have defaults; see SandboxConfig
    sandbox: SandboxConfig = field(default_factory=lambda: SandboxConfig.from_environment(os.environ))

    def __post_init__(self):
        for name in REQUIRED_ENVIRONMENT:
            if getattr(self, name) is None:
                raise ValueError(f"Missing environment variable: {name}")


ENVIRONMENT = _ENVIRONMENT()

ALLOWED_CHARACTERS = string.ascii_letters + string.digits + "-_"
APP_DIRECTORY = Path(__file__).parent
def _root_path(request) -> dict:
    """Every template gets `root_path`, the prefix the app is mounted at, to build its URLs with."""
    return {"root_path": request.scope.get("root_path") or ""}


TEMPLATES = Jinja2Templates(directory=APP_DIRECTORY / "webapp" / "templates", context_processors=[_root_path])


def _static_version() -> str:
    """Content hash of the built stylesheet and the site's own scripts: browsers re-fetch them (?v=...) after
    every release that changes one."""
    import hashlib

    try:
        css = (APP_DIRECTORY / "webapp" / "static" / "output.css").read_bytes()
        css += (APP_DIRECTORY / "webapp" / "scripts" / "meta-editors.js").read_bytes()
    except OSError:
        return "0"
    return hashlib.sha256(css).hexdigest()[:12]


TEMPLATES.env.globals["static_version"] = _static_version()


def _commit_sha() -> str:
    """The commit the running image was built from: PYTOOLS_COMMIT, else the file the image build
    writes (containers/Containerfile.prod), else "dev" outside the image."""
    if os.environ.get("PYTOOLS_COMMIT"):
        return os.environ["PYTOOLS_COMMIT"]
    try:
        return Path("/etc/catalog-commit").read_text().strip() or "dev"
    except OSError:
        return "dev"


TEMPLATES.env.globals["commit_sha"] = _commit_sha()


def _app_version() -> str:
    """The semantic version from server/pyproject.toml (the installed package metadata)."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("cadquery-catalog")
    except PackageNotFoundError:
        return "0.0.0"


TEMPLATES.env.globals["app_version"] = _app_version()

logger = logging.getLogger("uvicorn.error")
