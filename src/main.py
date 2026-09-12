from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.config import get_session_secret, get_upload_dir
from src.deps import get_current_user
from src.routes.auth import router as auth_router
from src.routes.folders import router as folders_router
from src.routes.health import router as health_router
from src.routes.pages import router as pages_router

SRC_DIR = Path(__file__).resolve().parent


def create_app() -> FastAPI:
    app = FastAPI(title="Projeto TLC", dependencies=[Depends(get_current_user)])
    app.add_middleware(
        SessionMiddleware,
        secret_key=get_session_secret(),
        same_site="lax",
        https_only=False,
    )
    app.mount("/static", StaticFiles(directory=SRC_DIR / "static"), name="static")
    upload_dir = get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(folders_router)
    app.include_router(pages_router)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=True)
