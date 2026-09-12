import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import Folder, User
from src.services.passwords import hash_password


def _create_user(db_session: Session, username: str = "alice") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("secret123"),
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_folder_persists_with_defaults(db_session: Session) -> None:
    user = _create_user(db_session)

    folder = Folder(
        title="Minhas Fotos",
        slug="minhas-fotos",
        owner_id=user.id,
    )
    db_session.add(folder)
    db_session.commit()

    stored = db_session.get(Folder, folder.id)
    assert stored is not None
    assert stored.title == "Minhas Fotos"
    assert stored.slug == "minhas-fotos"
    assert stored.description is None
    assert stored.is_public is True
    assert stored.is_adult is False
    assert stored.owner_id == user.id
    assert stored.created_at is not None
    assert stored.owner.id == user.id


def test_folder_slug_must_be_unique(db_session: Session) -> None:
    user = _create_user(db_session)

    folder1 = Folder(
        title="Viagem",
        slug="viagem-2026",
        owner_id=user.id,
    )
    db_session.add(folder1)
    db_session.commit()

    folder2 = Folder(
        title="Outra Viagem",
        slug="viagem-2026",
        owner_id=user.id,
    )
    db_session.add(folder2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_folder_user_relationship_and_cascade_delete(db_session: Session) -> None:
    user = _create_user(db_session)

    folder = Folder(
        title="Paisagens",
        slug="paisagens",
        owner=user,
        description="Belas paisagens",
        is_public=False,
        is_adult=True,
    )
    db_session.add(folder)
    db_session.commit()

    assert folder in user.folders
    folder_id = folder.id

    # Deletar o usuário deve deletar a pasta em cascata
    db_session.delete(user)
    db_session.commit()

    assert db_session.get(Folder, folder_id) is None
