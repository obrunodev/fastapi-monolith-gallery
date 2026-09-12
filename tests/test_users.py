import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models import User, UserRole
from src.services.passwords import hash_password
from src.services.seed import seed_admin


def test_user_persists_with_default_role(db_session: Session) -> None:
    user = User(
        username="alice",
        email="alice@example.com",
        password_hash=hash_password("secret"),
    )
    db_session.add(user)
    db_session.commit()

    stored = db_session.get(User, user.id)
    assert stored is not None
    assert stored.username == "alice"
    assert stored.email == "alice@example.com"
    assert stored.role == UserRole.USER
    assert stored.created_at is not None


def test_username_must_be_unique(db_session: Session) -> None:
    db_session.add(
        User(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("secret"),
        )
    )
    db_session.commit()
    db_session.add(
        User(
            username="alice",
            email="outra@example.com",
            password_hash=hash_password("secret"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_email_must_be_unique(db_session: Session) -> None:
    db_session.add(
        User(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("secret"),
        )
    )
    db_session.commit()
    db_session.add(
        User(
            username="bob",
            email="alice@example.com",
            password_hash=hash_password("secret"),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_seed_admin_creates_admin_user(db_session: Session) -> None:
    created = seed_admin(
        db_session,
        username="admin",
        email="admin@localhost",
        password="admin",
    )
    db_session.commit()

    assert created is not None
    assert created.username == "admin"
    assert created.email == "admin@localhost"
    assert created.role == UserRole.ADMIN
    assert created.password_hash != "admin"


def test_seed_admin_is_idempotent(db_session: Session) -> None:
    first = seed_admin(
        db_session,
        username="admin",
        email="admin@localhost",
        password="admin",
    )
    db_session.commit()
    second = seed_admin(
        db_session,
        username="admin",
        email="admin@localhost",
        password="admin",
    )
    db_session.commit()

    assert first is not None
    assert second is None
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_seed_admin_rejects_empty_password(db_session: Session) -> None:
    with pytest.raises(ValueError, match="senha"):
        seed_admin(
            db_session,
            username="admin",
            email="admin@localhost",
            password="",
        )
