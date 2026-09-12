from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.db import get_db
from src.schemas.auth import UserLogin, UserRegister
from src.services.auth import (
    SESSION_USER_ID,
    AuthError,
    authenticate_user,
    register_user,
)
from src.templating import templates

router = APIRouter(tags=["auth"])


def _is_logged_in(request: Request) -> bool:
    return request.session.get(SESSION_USER_ID) is not None


def _first_validation_error(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Dados inválidos."
    message = errors[0]["msg"]
    if message.startswith("Value error, "):
        message = message.removeprefix("Value error, ")
    return message


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "title": "Criar conta",
            "error": None,
            "username": "",
            "email": "",
        },
    )


@router.post("/register")
def register(
    request: Request,
    username: str = Form(),
    email: str = Form(),
    password: str = Form(),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if _is_logged_in(request):
        return RedirectResponse("/", status_code=303)
    context = {
        "title": "Criar conta",
        "username": username,
        "email": email,
        "error": None,
    }
    try:
        data = UserRegister(username=username, email=email, password=password)
        user = register_user(
            db,
            username=data.username,
            email=str(data.email),
            password=data.password,
        )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        context["error"] = _first_validation_error(exc)
        return templates.TemplateResponse(
            request,
            "register.html",
            context,
            status_code=400,
        )
    except AuthError as exc:
        db.rollback()
        context["error"] = exc.message
        return templates.TemplateResponse(
            request,
            "register.html",
            context,
            status_code=400,
        )

    request.session[SESSION_USER_ID] = user.id
    return RedirectResponse("/", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "title": "Entrar",
            "error": None,
            "identifier": "",
        },
    )


@router.post("/login")
def login(
    request: Request,
    identifier: str = Form(),
    password: str = Form(),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if _is_logged_in(request):
        return RedirectResponse("/", status_code=303)
    context = {
        "title": "Entrar",
        "identifier": identifier,
        "error": None,
    }
    try:
        data = UserLogin(identifier=identifier, password=password)
        user = authenticate_user(
            db,
            identifier=data.identifier,
            password=data.password,
        )
    except ValidationError as exc:
        context["error"] = _first_validation_error(exc)
        return templates.TemplateResponse(
            request,
            "login.html",
            context,
            status_code=400,
        )
    except AuthError as exc:
        context["error"] = exc.message
        return templates.TemplateResponse(
            request,
            "login.html",
            context,
            status_code=400,
        )

    request.session[SESSION_USER_ID] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/", status_code=303)
