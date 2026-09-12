import bcrypt
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.config import get_admin_email, get_admin_password, get_admin_username
from src.db import SessionLocal
from src.models import User, UserRole


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_admin(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
) -> User | None:
    """Cria o admin inicial se username ou e-mail ainda não existirem."""
    if not password:
        raise ValueError("A senha do admin não pode ser vazia.")

    existing = session.scalar(
        select(User).where(or_(User.username == username, User.email == email))
    )
    if existing is not None:
        return None

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.ADMIN,
    )
    session.add(user)
    session.flush()
    return user


def run() -> None:
    session = SessionLocal()
    try:
        created = seed_admin(
            session,
            username=get_admin_username(),
            email=get_admin_email(),
            password=get_admin_password(),
        )
        session.commit()
        if created is None:
            print("Admin já existe; seed ignorado.")
        else:
            print(f"Admin criado: {created.username} ({created.email})")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run()
