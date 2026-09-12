from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models import User, UserRole
from src.services.passwords import hash_password, verify_password

SESSION_USER_ID = "user_id"


class AuthError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def register_user(
    session: Session,
    *,
    username: str,
    email: str,
    password: str,
) -> User:
    existing = session.scalar(
        select(User).where(or_(User.username == username, User.email == email))
    )
    if existing is not None:
        if existing.username == username:
            raise AuthError("Este username já está em uso.")
        raise AuthError("Este e-mail já está em uso.")

    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role=UserRole.USER,
    )
    session.add(user)
    session.flush()
    return user


def authenticate_user(session: Session, *, identifier: str, password: str) -> User:
    user = session.scalar(
        select(User).where(or_(User.username == identifier, User.email == identifier))
    )
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Username ou senha inválidos.")
    return user
