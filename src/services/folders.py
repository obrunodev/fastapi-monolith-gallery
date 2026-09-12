import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.models import Folder
from src.schemas.folder import FolderCreate


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

