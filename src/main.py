from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.routes.health import router as health_router
from src.routes.pages import router as pages_router

SRC_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="Projeto TLC")
    app.mount("/static", StaticFiles(directory=SRC_DIR / "static"), name="static")
    app.include_router(health_router)
    app.include_router(pages_router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
