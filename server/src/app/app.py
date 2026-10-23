from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pathlib import Path

from app.models.tools import create_db_and_tables
from app.routes import tools, auth, upload, user, admin, metadata
from app import logger, ENVIRONMENT


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
APP_DIRECTORY = Path(__file__).parent / "webapp"
app.mount("/static", StaticFiles(directory=APP_DIRECTORY / "static"), name="static")
app.mount("/scripts", StaticFiles(directory=APP_DIRECTORY / "scripts"), name="scripts")
app.mount("/webfonts", StaticFiles(directory=APP_DIRECTORY / "webfonts"), name="webfonts")

app.include_router(upload.router)
app.include_router(auth.router)
app.include_router(tools.router)
app.include_router(user.router)
app.include_router(admin.router)
app.include_router(metadata.router)
# a cookie name and path of its own: PyTools lives on the same host under another prefix, and two
# apps sharing the default "session" cookie at path "/" would log each other out
app.add_middleware(
    SessionMiddleware,
    secret_key=ENVIRONMENT.SESSION_KEY,
    session_cookie="catalog_session",
    path=ENVIRONMENT.ROOT_PATH or "/",
)


for route in app.routes:
    # mounts and included routers carry no HTTP methods
    methods = getattr(route, "methods", None)
    if methods is None:
        continue
    logger.info(f"{methods} {route.path} {route.name}")
