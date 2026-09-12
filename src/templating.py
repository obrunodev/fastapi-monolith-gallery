from pathlib import Path

from starlette.requests import Request
from fastapi.templating import Jinja2Templates

from src.services.auth import SESSION_USER_ID

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _session_context(request: Request) -> dict[str, bool]:
    return {"logged_in": request.session.get(SESSION_USER_ID) is not None}


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR),
    context_processors=[_session_context],
)
