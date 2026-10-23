"""Browsing by category. /c/<category> lists the public models filed under any of its subcategories,
/c/<category>/<subcategory> one leaf, /c/misc everything unfiled. The pages are the front page with a
breadcrumb, the category's description, and its search and list scoped to the category."""

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import func
from sqlmodel import Session, select

from app import TEMPLATES, categories
from app.metadata.categories import model_ids_in
from app.models.tools import SessionDep, Tool

router = APIRouter()


def category_counts(session: Session) -> dict[str, int]:
    """Public models per leaf path and per top-level slug; a model counts once in each place it is filed."""

    def count(paths: list[str]) -> int:
        statement = select(func.count(Tool.id)).where(Tool.public == True, Tool.id.in_(model_ids_in(paths)))  # noqa: E712
        return session.exec(statement).one()

    counts = {}
    for category in categories.TREE:
        under = categories.paths_under(category.slug)
        counts[category.slug] = count(under)
        for path in under:
            counts[path] = count([path]) if path != category.slug else counts[category.slug]
    return counts


def category_bar(session: Session, current: Optional[str]) -> list[dict]:
    """The front page's tree: every category with its count and its subcategories; the current one is open."""
    counts = category_counts(session)
    return [
        {
            "slug": c.slug,
            "name": c.name,
            "count": counts[c.slug],
            "open": current is not None and current.split("/")[0] == c.slug,
            "subs": [{"path": s.path, "name": s.name, "count": counts[s.path]} for s in c.subcategories],
        }
        for c in categories.TREE
    ]


def index_page(request: Request, session: Session, category: Optional[str] = None, search: str = ""):
    """The front page; with `category`, that category's page (callers check it exists)."""
    crumbs, description = [], ""
    if category is not None:
        top, _, sub = category.partition("/")
        crumbs = [(categories.find(top).name, f"/c/{top}")]
        if sub:
            crumbs.append((categories.find(category).name, f"/c/{category}"))
        description = categories.find(category).description
    return TEMPLATES.TemplateResponse(
        request,
        "pages/index.html",
        {
            "header_title": "CadQuery Catalog",
            "request": request,
            "root_path": request.scope.get("root_path"),
            "search": search,
            "category": category,
            "crumbs": crumbs,
            "description": description,
            "bar": category_bar(session, category),
        },
    )


@router.get("/c/{category}", response_class=HTMLResponse)
async def category_page(request: Request, category: str, session: SessionDep, search: str = ""):
    if "/" in category or categories.find(category) is None:
        raise HTTPException(status_code=404, detail="Category Not Found")
    return index_page(request, session, category, search)


@router.get("/c/{category}/{subcategory}", response_class=HTMLResponse)
async def subcategory_page(request: Request, category: str, subcategory: str, session: SessionDep, search: str = ""):
    path = f"{category}/{subcategory}"
    if not categories.is_leaf(path):
        raise HTTPException(status_code=404, detail="Category Not Found")
    return index_page(request, session, path, search)
