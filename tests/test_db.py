from sqlalchemy import text
from sqlalchemy.orm import Session

from src.db import get_db


def test_engine_connects(db_session: Session) -> None:
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


def test_get_db_yields_session() -> None:
    generator = get_db()
    session = next(generator)
    try:
        assert isinstance(session, Session)
        assert session.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        generator.close()
