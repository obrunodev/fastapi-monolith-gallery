import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models import Folder, User
from src.schemas.folder import FolderCreate
from src.services import folders as folders_service
from src.services.auth import register_user


@pytest.fixture
def test_user(db_session: Session) -> User:
    user = register_user(
        db_session,
        username="john_doe",
        email="john@example.com",
        password="securePassword123",
    )
    db_session.commit()
    db_session.refresh(user)
    return user


# --- Testes de Service: slugify e unicidade ---


def test_slugify_accents_and_special_chars() -> None:
    assert folders_service.slugify("Viagem à Serra & Mar!!") == "viagem-a-serra-mar"
    assert folders_service.slugify("  Fotos 2024 / Rio  ") == "fotos-2024-rio"
    assert folders_service.slugify("---") == "pasta"
    assert folders_service.slugify("!@#$%") == "pasta"


def test_generate_unique_slug(db_session: Session, test_user: User) -> None:
    # 1ª pasta com título 'Férias'
    slug1 = folders_service.generate_unique_slug(db_session, "Férias")
    assert slug1 == "ferias"

    f1 = Folder(title="Férias", slug=slug1, owner_id=test_user.id)
    db_session.add(f1)
    db_session.commit()

    # 2ª pasta com mesmo título
    slug2 = folders_service.generate_unique_slug(db_session, "Férias")
    assert slug2 == "ferias-2"

    f2 = Folder(title="Férias", slug=slug2, owner_id=test_user.id)
    db_session.add(f2)
    db_session.commit()

    # 3ª pasta com mesmo título
    slug3 = folders_service.generate_unique_slug(db_session, "Férias")
    assert slug3 == "ferias-3"


def test_create_folder_service(db_session: Session, test_user: User) -> None:
    data = FolderCreate(
        title="Álbum de Família",
        description="Momentos inesquecíveis",
        is_public=True,
        is_adult=False,
    )
    folder = folders_service.create_folder(db_session, owner_id=test_user.id, data=data)
    db_session.commit()

    assert folder.id is not None
    assert folder.title == "Álbum de Família"
    assert folder.slug == "album-de-familia"
    assert folder.description == "Momentos inesquecíveis"
    assert folder.owner_id == test_user.id
    assert folder.is_public is True
    assert folder.is_adult is False

    retrieved = folders_service.get_folder_by_slug(db_session, "album-de-familia")
    assert retrieved is not None
    assert retrieved.id == folder.id

    by_id = folders_service.get_folder_by_id(db_session, folder.id)
    assert by_id is not None
    assert by_id.slug == folder.slug


# --- Testes de API JSON: POST /folders ---


def test_api_create_folder_requires_authentication(client: TestClient) -> None:
    response = client.post("/folders", json={"title": "Viagem"})
    assert response.status_code == 401
    assert "Autenticação necessária" in response.json()["detail"]


def test_api_create_folder_success(client: TestClient) -> None:
    # Cadastra e autentica usuário
    client.post(
        "/register",
        data={"username": "bob", "email": "bob@example.com", "password": "password123"},
    )

    payload = {
        "title": "Minha Galeria 2026",
        "description": "Fotos do projeto",
        "is_public": False,
        "is_adult": True,
    }
    response = client.post("/folders", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] is not None
    assert data["title"] == "Minha Galeria 2026"
    assert data["slug"] == "minha-galeria-2026"
    assert data["description"] == "Fotos do projeto"
    assert data["is_public"] is False
    assert data["is_adult"] is True
    assert "created_at" in data


def test_api_create_folder_unique_slug_increment(client: TestClient) -> None:
    client.post(
        "/register",
        data={"username": "clara", "email": "clara@example.com", "password": "password123"},
    )

    r1 = client.post("/folders", json={"title": "Projetos"})
    assert r1.status_code == 201
    assert r1.json()["slug"] == "projetos"

    r2 = client.post("/folders", json={"title": "Projetos"})
    assert r2.status_code == 201
    assert r2.json()["slug"] == "projetos-2"


def test_api_create_folder_validation_errors(client: TestClient) -> None:
    client.post(
        "/register",
        data={"username": "dan", "email": "dan@example.com", "password": "password123"},
    )

    # Título vazio
    r_empty = client.post("/folders", json={"title": "   "})
    assert r_empty.status_code == 422

    # Título excessivamente longo
    r_long = client.post("/folders", json={"title": "A" * 101})
    assert r_long.status_code == 422


# --- Testes de Telas e Formulários Web: GET/POST /folders/new ---


def test_web_folder_new_anonymous_redirects_to_login(client: TestClient) -> None:
    response = client.get("/folders/new", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_web_folder_new_logged_in_renders_form(client: TestClient) -> None:
    client.post(
        "/register",
        data={"username": "elena", "email": "elena@example.com", "password": "password123"},
    )

    response = client.get("/folders/new")
    assert response.status_code == 200
    assert "Nova Pasta" in response.text
    assert 'name="title"' in response.text
    assert 'name="description"' in response.text
    assert 'name="is_public"' in response.text
    assert 'name="is_adult"' in response.text


def test_web_submit_folder_form_validation_error(client: TestClient) -> None:
    client.post(
        "/register",
        data={"username": "felipe", "email": "felipe@example.com", "password": "password123"},
    )

    response = client.post(
        "/folders/new",
        data={"title": "   ", "description": "inválido"},
    )
    assert response.status_code == 400
    assert "O título da pasta não pode ser vazio" in response.text


def test_web_submit_folder_form_success(client: TestClient) -> None:
    client.post(
        "/register",
        data={"username": "gabriel", "email": "gabriel@example.com", "password": "password123"},
    )

    response = client.post(
        "/folders/new",
        data={
            "title": "Minha Primeira Pasta",
            "description": "Testando formulário web",
            "is_public": "true",
            "is_adult": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    # Ao seguir o redirecionamento, a mensagem flash de sucesso deve estar visível
    feed_res = client.get("/")
    assert "Pasta &#39;Minha Primeira Pasta&#39; criada com sucesso!" in feed_res.text or "Pasta 'Minha Primeira Pasta' criada com sucesso!" in feed_res.text


def test_nav_shows_new_folder_link_when_logged_in(client: TestClient) -> None:
    # Não logado: não deve conter o link "Nova pasta"
    r_anon = client.get("/")
    assert "/folders/new" not in r_anon.text

    # Logado: deve conter o link "Nova pasta"
    client.post(
        "/register",
        data={"username": "helen", "email": "helen@example.com", "password": "password123"},
    )
    r_user = client.get("/")
    assert "/folders/new" in r_user.text
