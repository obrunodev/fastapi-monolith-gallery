from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.db import get_db
from src.deps import get_current_user
from src.flash import flash
from src.models import User
from src.schemas.folder import FolderCreate, FolderRead
from src.services import folders as folders_service
from src.templating import templates

router = APIRouter(tags=["folders"])


@router.post("/folders", response_model=FolderRead, status_code=status.HTTP_201_CREATED)
def create_folder(
    data: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> FolderRead:
    """Cria uma nova pasta para o usuário autenticado via API JSON."""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação necessária para criar pastas.",
        )

    folder = folders_service.create_folder(db, owner_id=current_user.id, data=data)
    db.commit()
    db.refresh(folder)
    return folder


@router.get("/folders/new", response_model=None)
def folder_create_page(
    request: Request,
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
    """Exibe o formulário de criação de pasta (requer autenticação)."""
    if current_user is None:
        flash(request, "Faça login para criar uma pasta.")
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "folder_create.html",
        {
            "title": "Nova Pasta",
            "error": None,
            "title_value": "",
            "description_value": "",
            "is_public": True,
            "is_adult": False,
        },
    )


@router.post("/folders/new", response_model=None)
def submit_folder_create_form(
    request: Request,
    title: str = Form(""),
    description: str | None = Form(None),
    is_public: str | None = Form(None),
    is_adult: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
    """Processa a criação de pasta via formulário HTML."""
    if current_user is None:
        flash(request, "Faça login para criar uma pasta.")
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    is_public_val = is_public in {"true", "on", "1"}
    is_adult_val = is_adult in {"true", "on", "1"}

    context = {
        "title": "Nova Pasta",
        "error": None,
        "title_value": title,
        "description_value": description or "",
        "is_public": is_public_val,
        "is_adult": is_adult_val,
    }

    try:
        data = FolderCreate(
            title=title,
            description=description,
            is_public=is_public_val,
            is_adult=is_adult_val,
        )
        folder = folders_service.create_folder(db, owner_id=current_user.id, data=data)
        db.commit()
    except ValidationError as exc:
        db.rollback()
        errors = exc.errors()
        msg = errors[0]["msg"] if errors else "Dados inválidos."
        if msg.startswith("Value error, "):
            msg = msg.removeprefix("Value error, ")
        context["error"] = msg
        return templates.TemplateResponse(
            request,
            "folder_create.html",
            context,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    flash(request, f"Pasta '{folder.title}' criada com sucesso!")
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
