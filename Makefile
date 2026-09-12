.PHONY: install run test db-migrate db-upgrade

install:
	uv sync --group dev

run:
	uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

test:
	uv run pytest

db-migrate:
	uv run alembic revision --autogenerate -m "$(msg)"

db-upgrade:
	uv run alembic upgrade head
