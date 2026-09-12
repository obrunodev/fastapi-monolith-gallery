import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from src.models import Folder, Photo
from src.schemas.folder import FolderCreate
from src.services import storage


def slugify(text: str) -> str:
    """Converte uma string em um slug ASCII seguro para URL."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s-]", "", normalized).strip().lower()
    slug = re.sub(r"[-\s]+", "-", cleaned).strip("-")
    return slug or "pasta"


def generate_unique_slug(db: Session, title: str) -> str:
    """Gera um slug único globalmente para a pasta a partir do título."""
    base_slug = slugify(title)[:80] or "pasta"
    slug = base_slug
    counter = 1
    while db.scalar(select(Folder.id).where(Folder.slug == slug)) is not None:
        counter += 1
        slug = f"{base_slug[:70]}-{counter}"
    return slug


def create_folder(
    db: Session,
    owner_id: int,
    data: FolderCreate,
) -> Folder:
    """Cria uma nova pasta associada ao usuário proprietário."""
    slug = generate_unique_slug(db, data.title)
    folder = Folder(
        title=data.title,
        slug=slug,
        description=data.description,
        owner_id=owner_id,
        is_public=data.is_public,
        is_adult=data.is_adult,
    )
    db.add(folder)
    db.flush()
    return folder


def get_folder_by_slug(db: Session, slug: str) -> Folder | None:
    """Busca uma pasta pelo seu slug único."""
    return db.scalar(select(Folder).where(Folder.slug == slug))


def get_folder_by_id(db: Session, folder_id: int) -> Folder | None:
    """Busca uma pasta pelo seu ID."""
    return db.scalar(select(Folder).where(Folder.id == folder_id))


def list_user_folders(db: Session, owner_id: int) -> list[Folder]:
    """Lista todas as pastas pertencentes a um usuário, ordenadas pelas mais recentes."""
    stmt = (
        select(Folder)
        .where(Folder.owner_id == owner_id)
        .options(selectinload(Folder.photos))
        .order_by(Folder.created_at.desc(), Folder.id.desc())
    )
    return list(db.scalars(stmt).all())


def get_folder_by_slug_or_id(db: Session, identifier: str | int) -> Folder | None:
    """Busca uma pasta por slug ou id numérico."""
    if isinstance(identifier, int):
        return get_folder_by_id(db, identifier)
    folder = get_folder_by_slug(db, identifier)
    if folder is None and identifier.isdigit():
        folder = get_folder_by_id(db, int(identifier))
    return folder


def get_folder_photos(db: Session, folder_id: int) -> list[Photo]:
    """Retorna todas as fotos de uma pasta ordenadas por order asc."""
    stmt = select(Photo).where(Photo.folder_id == folder_id).order_by(Photo.order.asc(), Photo.id.asc())
    return list(db.scalars(stmt).all())


def get_photo_in_folder(db: Session, folder_id: int, photo_id: int) -> Photo | None:
    """Busca uma foto garantindo que ela pertence à pasta indicada."""
    return db.scalar(select(Photo).where(Photo.id == photo_id, Photo.folder_id == folder_id))


def add_photo_to_folder(
    db: Session,
    folder: Folder,
    content: bytes,
    original_filename: str | None = None,
    content_type: str | None = None,
) -> Photo:
    """Valida, salva a imagem em disco e insere o registro da foto com a próxima ordem disponível."""
    saved_filename, validated = storage.save_image(
        content=content,
        original_filename=original_filename,
        content_type=content_type,
    )

    try:
        current_max = db.scalar(
            select(func.coalesce(func.max(Photo.order), -1)).where(Photo.folder_id == folder.id)
        )
        next_order = (current_max if current_max is not None else -1) + 1

        photo = Photo(
            folder_id=folder.id,
            filename=saved_filename,
            original_name=validated.original_name,
            order=next_order,
        )
        db.add(photo)
        db.flush()
        return photo
    except Exception:
        storage.delete_file(saved_filename)
        raise


def remove_photo_from_folder(db: Session, folder: Folder, photo_id: int) -> str | None:
    """Remove a foto da pasta no banco e renumera a ordem das restantes.

    Retorna o filename em disco para exclusão após commit bem-sucedido.
    """
    photo = get_photo_in_folder(db, folder.id, photo_id)
    if photo is None:
        return None

    filename = photo.filename
    db.delete(photo)
    db.flush()

    remaining_photos = list(
        db.scalars(
            select(Photo).where(Photo.folder_id == folder.id).order_by(Photo.order.asc(), Photo.id.asc())
        ).all()
    )
    for idx, p in enumerate(remaining_photos):
        p.order = idx
    db.flush()
    return filename


def purge_photo_file(filename: str) -> None:
    """Remove o arquivo físico de uma foto após persistência confirmada."""
    storage.delete_file(filename)


def cleanup_photo_files(photos: list[Photo]) -> None:
    """Remove arquivos em disco de fotos cujo registro foi revertido."""
    for photo in photos:
        storage.delete_file(photo.filename)


def reorder_folder_photos(
    db: Session,
    folder: Folder,
    ordered_photo_ids: list[int],
) -> list[Photo]:
    """Atualiza a ordenação das fotos da pasta conforme a lista de IDs recebida."""
    current_photos = list(
        db.scalars(select(Photo).where(Photo.folder_id == folder.id)).all()
    )
    photos_by_id = {p.id: p for p in current_photos}

    if len(ordered_photo_ids) != len(current_photos):
        raise ValueError("Informe todos os IDs das fotos da pasta para reordenar.")

    if len(ordered_photo_ids) != len(set(ordered_photo_ids)):
        raise ValueError("A lista de fotos contém IDs duplicados.")

    for pid in ordered_photo_ids:
        if pid not in photos_by_id:
            raise ValueError(f"A foto {pid} não pertence a esta pasta.")

    for idx, pid in enumerate(ordered_photo_ids):
        photos_by_id[pid].order = idx

    db.flush()
    return list(
        db.scalars(
            select(Photo).where(Photo.folder_id == folder.id).order_by(Photo.order.asc(), Photo.id.asc())
        ).all()
    )


def move_photo_order(
    db: Session,
    folder: Folder,
    photo_id: int,
    direction: str,
) -> bool:
    """Move uma foto uma posição para cima ('up') ou para baixo ('down')."""
    if direction not in {"up", "down"}:
        raise ValueError("Direção inválida. Use 'up' ou 'down'.")

    photos = list(
        db.scalars(
            select(Photo).where(Photo.folder_id == folder.id).order_by(Photo.order.asc(), Photo.id.asc())
        ).all()
    )
    matching_indices = [i for i, p in enumerate(photos) if p.id == photo_id]
    if not matching_indices:
        return False

    idx = matching_indices[0]
    if direction == "up" and idx > 0:
        photos[idx], photos[idx - 1] = photos[idx - 1], photos[idx]
    elif direction == "down" and idx < len(photos) - 1:
        photos[idx], photos[idx + 1] = photos[idx + 1], photos[idx]
    else:
        return False

    for new_order, p in enumerate(photos):
        p.order = new_order

    db.flush()
    return True


