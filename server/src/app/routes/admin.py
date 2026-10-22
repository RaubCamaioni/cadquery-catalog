"""Admin page: every account and its tools, with a ban switch per account.

Who is an admin is a column on the user table (`user.admin`), set in the database; nothing
in the code names an account. Non-admins get a 404, like a private tool.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app import TEMPLATES
from app.models import tools as db
from app.routes.auth import session_user

router = APIRouter()


def require_admin(request: Request) -> db.User:
    user = session_user(request)
    if user is None or not user.admin:
        raise HTTPException(status_code=404, detail="Not Found")
    return user


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, session: db.SessionDep):
    require_admin(request)
    return TEMPLATES.TemplateResponse(
        request,
        "pages/admin.html",
        {
            "header_title": "CadQuery Catalog",
            "request": request,
            "root_path": request.scope.get("root_path"),
            "accounts": db.get_users_with_tools(session),
        },
    )


@router.post("/admin/ban/{user_id}", response_class=HTMLResponse)
async def ban_user(request: Request, user_id: int, months: int, session: db.SessionDep):
    """Ban for 1, 6 or 12 months: the account cannot log in and all its tools go private."""
    admin = require_admin(request)
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot ban yourself")
    if months not in db.BAN_PERIODS_MONTHS:
        raise HTTPException(status_code=400, detail="Ban period must be 1, 6 or 12 months")
    db.set_banned(session, user_id, months)
    return HTMLResponse(status_code=200)


@router.post("/admin/unban/{user_id}", response_class=HTMLResponse)
async def unban_user(request: Request, user_id: int, session: db.SessionDep):
    require_admin(request)
    db.set_banned(session, user_id, None)
    return HTMLResponse(status_code=200)
