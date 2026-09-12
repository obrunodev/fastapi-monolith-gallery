from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from src.db import Base, get_db


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


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
