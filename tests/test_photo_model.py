import pytest
from sqlalchemy.orm import Session

from src.models import Folder, Photo, User
from src.services.passwords import hash_password


def _create_user_and_folder(db_session: Session, username: str = "alice", slug: str = "minhas-fotos") -> tuple[User, Folder]:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password("secret123"),
    )
    db_session.add(user)
    db_session.commit()

    folder = Folder(
        title="Minhas Fotos",
        slug=slug,
        owner_id=user.id,
    )
    db_session.add(folder)
    db_session.commit()
    return user, folder


def test_photo_persists_with_defaults(db_session: Session) -> None:
    _, folder = _create_user_and_folder(db_session)

    photo = Photo(
        folder_id=folder.id,
        filename="foto123_abc.jpg",
        original_name="paisagem.jpg",
    )
    db_session.add(photo)
    db_session.commit()

    stored = db_session.get(Photo, photo.id)
    assert stored is not None
    assert stored.filename == "foto123_abc.jpg"
    assert stored.original_name == "paisagem.jpg"
    assert stored.order == 0
    assert stored.folder_id == folder.id
    assert stored.created_at is not None
    assert stored.folder.id == folder.id


def test_photos_ordered_and_cascade_delete_on_folder(db_session: Session) -> None:
    _, folder = _create_user_and_folder(db_session)

    photo1 = Photo(
        folder=folder,
        filename="foto1.jpg",
        original_name="foto1.jpg",
        order=2,
    )
    photo2 = Photo(
        folder=folder,
        filename="foto2.jpg",
        original_name="foto2.jpg",
        order=1,
    )
    photo3 = Photo(
        folder=folder,
        filename="foto3.jpg",
        original_name="foto3.jpg",
        order=0,
    )
    db_session.add_all([photo1, photo2, photo3])
    db_session.commit()

    db_session.refresh(folder)
    assert len(folder.photos) == 3
    # Confirma que a ordenação respeita order crescente
    assert [p.filename for p in folder.photos] == ["foto3.jpg", "foto2.jpg", "foto1.jpg"]

    photo_ids = [photo1.id, photo2.id, photo3.id]

    # Deletar a pasta deve deletar as fotos da pasta em cascata
    db_session.delete(folder)
    db_session.commit()

    for pid in photo_ids:
        assert db_session.get(Photo, pid) is None


def test_photos_cascade_delete_on_user(db_session: Session) -> None:
    user, folder = _create_user_and_folder(db_session)

    photo = Photo(
        folder=folder,
        filename="foto_user_cascade.jpg",
        original_name="foto.jpg",
    )
    db_session.add(photo)
    db_session.commit()

    photo_id = photo.id

    # Deletar o dono da pasta deve deletar a pasta e a foto em cascata
    db_session.delete(user)
    db_session.commit()

    assert db_session.get(Photo, photo_id) is None
