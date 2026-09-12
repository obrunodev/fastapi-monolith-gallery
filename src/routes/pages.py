from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"title": "Dashboard"},
    )
