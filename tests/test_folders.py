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
    assert response.headers["location"] == "/me/folders"

    # Ao seguir o redirecionamento, a mensagem flash de sucesso deve estar visível
    feed_res = client.get("/me/folders")
    assert "Pasta &#39;Minha Primeira Pasta&#39; criada com sucesso!" in feed_res.text or "Pasta 'Minha Primeira Pasta' criada com sucesso!" in feed_res.text


def test_nav_shows_new_folder_link_when_logged_in(client: TestClient) -> None:
    # Não logado: não deve conter os links de pastas
    r_anon = client.get("/")
    assert "/folders/new" not in r_anon.text
    assert "/me/folders" not in r_anon.text

    # Logado: deve conter os links "Nova pasta" e "Minhas pastas"
    client.post(
        "/register",
        data={"username": "helen", "email": "helen@example.com", "password": "password123"},
    )
    r_user = client.get("/")
    assert "/folders/new" in r_user.text
    assert "/me/folders" in r_user.text


# --- Testes de Listagem de Pastas do Usuário: /me/folders ---


def test_list_user_folders_service(db_session: Session, test_user: User) -> None:
    # Usuário sem pastas
    folders = folders_service.list_user_folders(db_session, test_user.id)
    assert folders == []

    # Cria pasta 1
    f1 = folders_service.create_folder(
        db_session,
        owner_id=test_user.id,
        data=FolderCreate(title="Primeira Pasta", description="Desc 1", is_public=True),
    )
    db_session.commit()

    # Cria outro usuário com sua própria pasta
    other_user = register_user(
        db_session,
        username="other_user",
        email="other@example.com",
        password="password123",
    )
    db_session.commit()
    folders_service.create_folder(
        db_session,
        owner_id=other_user.id,
        data=FolderCreate(title="Pasta de Outro", is_public=True),
    )
    db_session.commit()

    # Cria pasta 2 do test_user
    f2 = folders_service.create_folder(
        db_session,
        owner_id=test_user.id,
        data=FolderCreate(title="Segunda Pasta", description="Desc 2", is_public=False, is_adult=True),
    )
    db_session.commit()

    # Deve retornar apenas as 2 pastas do test_user, com a mais recente primeiro
    user_folders = folders_service.list_user_folders(db_session, test_user.id)
    assert len(user_folders) == 2
    assert [f.id for f in user_folders] == [f2.id, f1.id]
    assert user_folders[0].title == "Segunda Pasta"
    assert user_folders[0].is_adult is True
    assert user_folders[0].is_public is False
    assert user_folders[1].title == "Primeira Pasta"


def test_list_folders_anonymous_redirects_to_login(client: TestClient) -> None:
    response = client.get("/me/folders", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    # Segue redirecionamento e verifica mensagem flash
    login_page = client.get("/login")
    assert "Faça login para ver suas pastas." in login_page.text


def test_list_folders_anonymous_api_returns_401(client: TestClient) -> None:
    response = client.get("/me/folders", headers={"Accept": "application/json"})
    assert response.status_code == 401
    assert "Autenticação necessária" in response.json()["detail"]


def test_list_folders_prefers_html_when_accept_lists_json_second(client: TestClient) -> None:
    client.post(
        "/register",
        data={"username": "laura", "email": "laura@example.com", "password": "password123"},
    )
    response = client.get(
        "/me/folders",
        headers={"Accept": "text/html, application/json;q=0.9"},
    )
    assert response.status_code == 200
    assert "Minhas Pastas" in response.text


def test_list_folders_logged_in_empty_state(client: TestClient) -> None:
    client.post(
        "/register",
        data={"username": "isabela", "email": "isabela@example.com", "password": "password123"},
    )

    # SSR
    response = client.get("/me/folders")
    assert response.status_code == 200
    assert "Minhas Pastas" in response.text
    assert "Você ainda não criou nenhuma pasta." in response.text
    assert "Criar primeira pasta" in response.text

    # JSON API
    api_response = client.get("/me/folders", headers={"Accept": "application/json"})
    assert api_response.status_code == 200
    assert api_response.json() == []


def test_list_folders_logged_in_with_folders(client: TestClient) -> None:
    # Usuário 1 cria duas pastas
    client.post(
        "/register",
        data={"username": "julio", "email": "julio@example.com", "password": "password123"},
    )
    client.post(
        "/folders",
        json={"title": "Viagem Chile", "description": "Fotos do Atacama", "is_public": True, "is_adult": False},
    )
    client.post(
        "/folders",
        json={"title": "Projetos Secretos", "description": "Confidencial", "is_public": False, "is_adult": True},
    )

    # SSR: deve exibir as pastas, badges e descrições
    ssr_response = client.get("/me/folders")
    assert ssr_response.status_code == 200
    assert "Viagem Chile" in ssr_response.text
    assert "Fotos do Atacama" in ssr_response.text
    assert "Projetos Secretos" in ssr_response.text
    assert "Pública" in ssr_response.text
    assert "Privada" in ssr_response.text
    assert "+18" in ssr_response.text

    # JSON API: deve retornar as 2 pastas ordenadas
    api_response = client.get("/me/folders", headers={"Accept": "application/json"})
    assert api_response.status_code == 200
    data = api_response.json()
    assert len(data) == 2
    assert data[0]["title"] == "Projetos Secretos"
    assert data[0]["is_public"] is False
    assert data[0]["is_adult"] is True
    assert data[1]["title"] == "Viagem Chile"
    assert data[1]["is_public"] is True
    assert data[1]["is_adult"] is False

