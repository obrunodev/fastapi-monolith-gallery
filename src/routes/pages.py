from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.db import get_db
from src.services import folders as folders_service
from src.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
def feed(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    folders = folders_service.list_recent_public_folders(db)
    return templates.TemplateResponse(
        request,
        "feed.html",
        {
            "title": "Galeria",
            "folders": folders,
        },
    )

