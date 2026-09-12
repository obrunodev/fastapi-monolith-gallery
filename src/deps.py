from fastapi import Depends, Request
from sqlalchemy.orm import Session

from src.db import get_db
from src.models import User
from src.services.auth import SESSION_USER_ID, get_user_by_id


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    """Usuário da sessão, ou None se a visita for anônima ou a sessão for inválida."""
    user_id = request.session.get(SESSION_USER_ID)
    if not isinstance(user_id, int):
        request.state.current_user = None
        return None

    user = get_user_by_id(db, user_id)
    if user is None:
        request.session.pop(SESSION_USER_ID, None)
        request.state.current_user = None
        return None

    request.state.current_user = user
    return user
