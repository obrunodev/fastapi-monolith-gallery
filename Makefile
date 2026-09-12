.PHONY: install run test

install:
	uv sync --group dev

run:
	uv run uvicorn src.main:app --reload --host 127.0.0.1 --port 8000

test:
	uv run pytest
