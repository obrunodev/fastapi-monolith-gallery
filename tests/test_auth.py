from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import User

REGISTER_DATA = {
    "username": "alice",
    "email": "alice@example.com",
    "password": "secret123",
}


def test_register_page_renders_form(client: TestClient) -> None:
    response = client.get("/register")
    assert response.status_code == 200
    assert "Criar conta" in response.text
    assert 'name="username"' in response.text


def test_login_page_renders_form(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "Entrar" in response.text
    assert 'name="identifier"' in response.text


def test_register_creates_session_and_redirects_home(client: TestClient) -> None:
    response = client.post("/register", data=REGISTER_DATA, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert client.cookies.get("session")


def test_register_rejects_duplicate_username(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    client.post("/logout")
    response = client.post(
        "/register",
        data={
            "username": "alice",
            "email": "outra@example.com",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "username já está em uso" in response.text


def test_login_with_username_redirects_home(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    client.post("/logout")
    response = client.post(
        "/login",
        data={"identifier": "alice", "password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_with_email_redirects_home(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    client.post("/logout")
    response = client.post(
        "/login",
        data={"identifier": "alice@example.com", "password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_rejects_wrong_password(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    client.post("/logout")
    response = client.post(
        "/login",
        data={"identifier": "alice", "password": "wrongpass"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Username ou senha inválidos" in response.text


def test_logout_clears_session(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    login_page = client.get("/login")
    assert "Você já está autenticado" not in login_page.text
    assert 'name="identifier"' in login_page.text


def test_home_shows_login_links_for_visitor(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Entrar" in response.text
    assert "Criar conta" in response.text
    assert ">Sair<" not in response.text


def test_home_shows_logout_after_login(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    response = client.get("/")
    assert response.status_code == 200
    assert ">Sair<" in response.text
    assert 'action="/logout"' in response.text
    assert 'class="site-nav-user">alice' in response.text
    assert 'href="/login"' not in response.text


def test_missing_user_is_treated_as_anonymous(
    client: TestClient,
    db_session: Session,
) -> None:
    client.post("/register", data=REGISTER_DATA)
    user = db_session.scalar(select(User).where(User.username == "alice"))
    assert user is not None
    db_session.delete(user)
    db_session.commit()

    response = client.get("/")
    assert response.status_code == 200
    assert "Entrar" in response.text
    assert ">Sair<" not in response.text


def test_register_flashes_once_on_home(client: TestClient) -> None:
    response = client.post("/register", data=REGISTER_DATA)
    assert response.status_code == 200
    assert "Conta criada." in response.text
    again = client.get("/")
    assert "Conta criada." not in again.text


def test_login_flashes_on_home(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    client.post("/logout")
    response = client.post(
        "/login",
        data={"identifier": "alice", "password": "secret123"},
    )
    assert response.status_code == 200
    assert "Você entrou." in response.text


def test_logout_flashes_on_home(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    response = client.post("/logout")
    assert response.status_code == 200
    assert "Você saiu." in response.text
    assert "Entrar" in response.text
