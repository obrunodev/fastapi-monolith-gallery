from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.deps import get_current_user
from src.models import User
from src.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"title": "Dashboard", "current_user": current_user},
    )
