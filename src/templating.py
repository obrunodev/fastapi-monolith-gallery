from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from src.flash import pop_flashes

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _session_context(request: Request) -> dict[str, object]:
    current_user = getattr(request.state, "current_user", None)
    return {
        "current_user": current_user,
        "logged_in": current_user is not None,
        "flashes": pop_flashes(request),
    }


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR),
    context_processors=[_session_context],
)
