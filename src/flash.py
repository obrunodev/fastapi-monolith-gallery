from starlette.requests import Request

FLASH_SESSION_KEY = "_flashes"


def flash(request: Request, message: str, category: str = "success") -> None:
    flashes = request.session.get(FLASH_SESSION_KEY, [])
    if not isinstance(flashes, list):
        flashes = []
    flashes.append({"message": message, "category": category})
    request.session[FLASH_SESSION_KEY] = flashes


def pop_flashes(request: Request) -> list[dict[str, str]]:
    raw = request.session.pop(FLASH_SESSION_KEY, [])
    if not isinstance(raw, list):
        return []

    flashes: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        category = item.get("category", "success")
        if isinstance(message, str) and message and isinstance(category, str):
            flashes.append({"message": message, "category": category})
    return flashes
