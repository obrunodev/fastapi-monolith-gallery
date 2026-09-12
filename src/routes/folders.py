from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.config import get_max_upload_size
from src.db import get_db
from src.deps import get_current_user
from src.flash import flash
from src.models import Folder, User
from src.schemas.folder import FolderCreate, FolderDetailRead, FolderRead
from src.schemas.photo import PhotoDeleteResponse, PhotoRead, PhotoReorderRequest
from src.services import folders as folders_service
from src.services.storage import StorageValidationError
from src.templating import templates

router = APIRouter(tags=["folders"])


def _wants_json(request: Request) -> bool:
    """Retorna True só quando o cliente pede JSON como media type primário."""
    accept = request.headers.get("accept", "")
    if not accept:
        return False
    primary = accept.split(",")[0].split(";")[0].strip().lower()
    return primary == "application/json" or primary.endswith("+json")


def _get_folder_or_404(db: Session, slug: str) -> Folder:
    folder = folders_service.get_folder_by_slug_or_id(db, slug)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada.")
    return folder


def _redirect_login_if_anonymous(
    request: Request,
    current_user: User | None,
    login_message: str,
) -> RedirectResponse | None:
    if current_user is None:
        flash(request, login_message)
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    return None


def _require_owned_folder(
    db: Session,
    slug: str,
    current_user: User,
    *,
    forbidden_detail: str,
) -> Folder:
    folder = _get_folder_or_404(db, slug)
    if folder.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail)
    return folder


def _require_owner_json(
    current_user: User | None,
    folder: Folder,
    *,
    auth_detail: str,
    forbidden_detail: str,
) -> User:
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=auth_detail)
    if folder.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=forbidden_detail)
    return current_user


@router.get("/me/folders", response_model=None)
def list_my_folders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse | JSONResponse:
    """Lista as pastas do usuário autenticado (HTML ou JSON)."""
    is_json = _wants_json(request)

    if current_user is None:
        if is_json:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Autenticação necessária para listar suas pastas.",
            )
        flash(request, "Faça login para ver suas pastas.")
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    folders = folders_service.list_user_folders(db, owner_id=current_user.id)

    if is_json:
        return JSONResponse(
            content=[FolderRead.model_validate(f).model_dump(mode="json") for f in folders]
        )

    return templates.TemplateResponse(
        request,
        "my_folders.html",
        {
            "title": "Minhas Pastas",
            "folders": folders,
        },
    )


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
    return RedirectResponse("/me/folders", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/folders/{slug}/edit", response_model=None)
def folder_edit_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
    """Exibe a tela de gerenciamento de fotos da pasta (upload, exclusão, reordenação)."""
    redirect = _redirect_login_if_anonymous(
        request, current_user, "Faça login para gerenciar suas pastas."
    )
    if redirect is not None:
        return redirect

    folder = _require_owned_folder(
        db,
        slug,
        current_user,
        forbidden_detail="Você não tem permissão para gerenciar esta pasta.",
    )

    photos = folders_service.get_folder_photos(db, folder.id)
    max_upload_mb = get_max_upload_size() // (1024 * 1024)

    return templates.TemplateResponse(
        request,
        "folder_edit.html",
        {
            "title": f"Gerenciar Fotos — {folder.title}",
            "folder": folder,
            "photos": photos,
            "max_upload_mb": max_upload_mb,
        },
    )


@router.post("/folders/{slug}/photos", response_model=None)
def add_photos_to_folder(
    slug: str,
    request: Request,
    files: list[UploadFile] = File(default=[]),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse | JSONResponse:
    """Adiciona uma ou mais fotos à pasta (aceita multipart/form-data via form HTML ou API)."""
    is_json = _wants_json(request)

    if current_user is None:
        if is_json:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Autenticação necessária para adicionar fotos.",
            )
        flash(request, "Faça login para adicionar fotos.")
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)

    folder = _get_folder_or_404(db, slug)
    _require_owner_json(
        current_user,
        folder,
        auth_detail="Autenticação necessária para adicionar fotos.",
        forbidden_detail="Você não tem permissão para adicionar fotos nesta pasta.",
    )

    upload_list: list[UploadFile] = []
    if file is not None and file.filename:
        upload_list.append(file)
    for f in files:
        if f.filename:
            upload_list.append(f)

    if not upload_list:
        if is_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nenhum arquivo enviado.",
            )
        flash(request, "Selecione pelo menos uma foto para enviar.", "error")
        return RedirectResponse(f"/folders/{folder.slug}/edit", status_code=status.HTTP_303_SEE_OTHER)

    created_photos = []
    try:
        for upload in upload_list:
            content = upload.file.read()
            photo = folders_service.add_photo_to_folder(
                db=db,
                folder=folder,
                content=content,
                original_filename=upload.filename,
                content_type=upload.content_type,
            )
            created_photos.append(photo)
        db.commit()
    except StorageValidationError as exc:
        db.rollback()
        folders_service.cleanup_photo_files(created_photos)
        if is_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        flash(request, str(exc), "error")
        return RedirectResponse(f"/folders/{folder.slug}/edit", status_code=status.HTTP_303_SEE_OTHER)
    except Exception:
        db.rollback()
        folders_service.cleanup_photo_files(created_photos)
        raise

    if is_json:
        if len(created_photos) == 1 and (file is not None or len(files) <= 1):
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=PhotoRead.model_validate(created_photos[0]).model_dump(mode="json"),
            )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=[PhotoRead.model_validate(p).model_dump(mode="json") for p in created_photos],
        )

    msg = (
        "Foto adicionada com sucesso!"
        if len(created_photos) == 1
        else f"{len(created_photos)} fotos adicionadas com sucesso!"
    )
    flash(request, msg)
    return RedirectResponse(f"/folders/{folder.slug}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.delete(
    "/folders/{slug}/photos/{photo_id}",
    status_code=status.HTTP_200_OK,
    response_model=PhotoDeleteResponse,
)
def delete_photo_api(
    slug: str,
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> PhotoDeleteResponse:
    """Remove uma foto da pasta via API JSON."""
    folder = _get_folder_or_404(db, slug)
    _require_owner_json(
        current_user,
        folder,
        auth_detail="Autenticação necessária para remover fotos.",
        forbidden_detail="Você não tem permissão para remover fotos desta pasta.",
    )

    filename = folders_service.remove_photo_from_folder(db, folder, photo_id)
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foto não encontrada nesta pasta.",
        )

    db.commit()
    folders_service.purge_photo_file(filename)
    return PhotoDeleteResponse(status="ok", message="Foto removida com sucesso.")


@router.post("/folders/{slug}/photos/{photo_id}/delete", response_model=None)
def delete_photo_form(
    slug: str,
    photo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
    """Remove uma foto da pasta via formulário HTML (sem JS)."""
    redirect = _redirect_login_if_anonymous(request, current_user, "Faça login para remover fotos.")
    if redirect is not None:
        return redirect

    folder = _require_owned_folder(
        db,
        slug,
        current_user,
        forbidden_detail="Você não tem permissão para remover fotos desta pasta.",
    )

    filename = folders_service.remove_photo_from_folder(db, folder, photo_id)
    if filename is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foto não encontrada nesta pasta.",
        )

    db.commit()
    folders_service.purge_photo_file(filename)
    flash(request, "Foto removida com sucesso!")
    return RedirectResponse(f"/folders/{folder.slug}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.put("/folders/{slug}/photos/order", response_model=list[PhotoRead])
def reorder_photos_api(
    slug: str,
    payload: PhotoReorderRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> list[PhotoRead]:
    """Reordena as fotos de uma pasta via PUT JSON."""
    folder = _get_folder_or_404(db, slug)
    _require_owner_json(
        current_user,
        folder,
        auth_detail="Autenticação necessária para reordenar fotos.",
        forbidden_detail="Você não tem permissão para alterar esta pasta.",
    )

    ordered_ids = folders_service.resolve_reorder_photo_ids(payload)
    try:
        updated = folders_service.reorder_folder_photos(db, folder, ordered_ids)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return [PhotoRead.model_validate(p) for p in updated]


@router.post("/folders/{slug}/photos/reorder", response_model=list[PhotoRead])
def reorder_photos_post_api(
    slug: str,
    payload: PhotoReorderRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> list[PhotoRead]:
    """Alias para reordenar fotos via POST JSON."""
    return reorder_photos_api(slug=slug, payload=payload, db=db, current_user=current_user)


@router.post("/folders/{slug}/photos/{photo_id}/move", response_model=None)
def move_photo_order_form(
    slug: str,
    photo_id: int,
    request: Request,
    direction: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
    """Move a foto uma posição acima ou abaixo via formulário HTML."""
    redirect = _redirect_login_if_anonymous(request, current_user, "Faça login para reordenar fotos.")
    if redirect is not None:
        return redirect

    folder = _require_owned_folder(
        db,
        slug,
        current_user,
        forbidden_detail="Você não tem permissão para alterar esta pasta.",
    )

    try:
        moved = folders_service.move_photo_order(db, folder, photo_id, direction)
        if moved:
            db.commit()
            flash(request, "Ordem atualizada com sucesso.")
        else:
            flash(request, "Não foi possível mover a foto.", "error")
    except ValueError as exc:
        flash(request, str(exc), "error")

    return RedirectResponse(f"/folders/{folder.slug}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/folders/{slug}", response_model=None)
def get_folder_page(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | JSONResponse:
    """Exibe os detalhes e fotos de uma pasta pública (ou privada se for o dono)."""
    is_json = _wants_json(request)

    folder = folders_service.get_folder_with_photos(db, slug)
    if folder is None or not folders_service.can_view_folder(folder, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pasta não encontrada.")

    if is_json:
        return JSONResponse(
            content=FolderDetailRead.model_validate(folder).model_dump(mode="json")
        )

    is_owner = current_user is not None and current_user.id == folder.owner_id

    return templates.TemplateResponse(
        request,
        "folder_detail.html",
        {
            "title": f"{folder.title} — Galeria",
            "folder": folder,
            "is_owner": is_owner,
        },
    )


