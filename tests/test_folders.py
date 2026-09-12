import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.config import get_upload_dir
from src.models import Folder, Photo, User
from src.schemas.folder import FolderCreate
from src.services import folders as folders_service
from src.services import storage
from src.services.auth import register_user

JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00fakejpegdata"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01fake"


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


# --- Testes da Tarefa 1.7: Gestão de Fotos (Adicionar, Remover, Reordenar) ---


def test_add_photo_service(db_session: Session, test_user: User) -> None:
    folder = folders_service.create_folder(
        db_session,
        owner_id=test_user.id,
        data=FolderCreate(title="Praia 2026"),
    )
    db_session.commit()

    # Adiciona 1ª foto
    photo1 = folders_service.add_photo_to_folder(
        db=db_session,
        folder=folder,
        content=JPEG_BYTES,
        original_filename="mar.jpg",
        content_type="image/jpeg",
    )
    db_session.commit()

    assert photo1.id is not None
    assert photo1.folder_id == folder.id
    assert photo1.original_name == "mar.jpg"
    assert photo1.order == 0
    assert storage.file_exists(photo1.filename) is True

    # Adiciona 2ª foto
    photo2 = folders_service.add_photo_to_folder(
        db=db_session,
        folder=folder,
        content=PNG_BYTES,
        original_filename="areia.png",
        content_type="image/png",
    )
    db_session.commit()

    assert photo2.id is not None
    assert photo2.folder_id == folder.id
    assert photo2.original_name == "areia.png"
    assert photo2.order == 1
    assert storage.file_exists(photo2.filename) is True

    # Limpa arquivos criados
    storage.delete_file(photo1.filename)
    storage.delete_file(photo2.filename)


def test_remove_photo_service(db_session: Session, test_user: User) -> None:
    folder = folders_service.create_folder(
        db_session,
        owner_id=test_user.id,
        data=FolderCreate(title="Montanha"),
    )
    db_session.commit()

    p1 = folders_service.add_photo_to_folder(db_session, folder, JPEG_BYTES, "p1.jpg")
    p2 = folders_service.add_photo_to_folder(db_session, folder, PNG_BYTES, "p2.png")
    db_session.commit()

    p1_filename = p1.filename
    p1_id = p1.id
    p2_id = p2.id
    assert storage.file_exists(p1_filename) is True

    # Remove p1
    filename = folders_service.remove_photo_from_folder(db_session, folder, p1_id)
    db_session.commit()
    assert filename == p1_filename
    folders_service.purge_photo_file(filename)

    assert storage.file_exists(p1_filename) is False
    assert folders_service.get_photo_in_folder(db_session, folder.id, p1_id) is None

    # p2 agora deve ter order reindexada para 0
    remaining = folders_service.get_folder_photos(db_session, folder.id)
    assert len(remaining) == 1
    assert remaining[0].id == p2_id
    assert remaining[0].order == 0

    # Limpa p2
    storage.delete_file(remaining[0].filename)


def test_reorder_photos_service(db_session: Session, test_user: User) -> None:
    folder = folders_service.create_folder(
        db_session,
        owner_id=test_user.id,
        data=FolderCreate(title="Galeria Ordenada"),
    )
    db_session.commit()

    p1 = folders_service.add_photo_to_folder(db_session, folder, JPEG_BYTES, "p1.jpg")
    p2 = folders_service.add_photo_to_folder(db_session, folder, PNG_BYTES, "p2.png")
    p3 = folders_service.add_photo_to_folder(db_session, folder, JPEG_BYTES, "p3.jpg")
    db_session.commit()

    # Reordena para [p3, p1, p2]
    reordered = folders_service.reorder_folder_photos(db_session, folder, [p3.id, p1.id, p2.id])
    db_session.commit()

    assert [p.id for p in reordered] == [p3.id, p1.id, p2.id]
    assert [p.order for p in reordered] == [0, 1, 2]

    # Lista parcial de IDs
    with pytest.raises(ValueError, match="Informe todos os IDs"):
        folders_service.reorder_folder_photos(db_session, folder, [p3.id, p1.id])

    # Tentativa de passar ID de foto que não existe ou de outra pasta
    with pytest.raises(ValueError, match="não pertence a esta pasta"):
        folders_service.reorder_folder_photos(db_session, folder, [p3.id, p1.id, 99999])

    # Tentativa de passar IDs duplicados
    with pytest.raises(ValueError, match="duplicados"):
        folders_service.reorder_folder_photos(db_session, folder, [p3.id, p3.id, p2.id])

    for p in reordered:
        storage.delete_file(p.filename)


def test_move_photo_order_service(db_session: Session, test_user: User) -> None:
    folder = folders_service.create_folder(
        db_session,
        owner_id=test_user.id,
        data=FolderCreate(title="Movendo Fotos"),
    )
    db_session.commit()

    p1 = folders_service.add_photo_to_folder(db_session, folder, JPEG_BYTES, "p1.jpg")
    p2 = folders_service.add_photo_to_folder(db_session, folder, PNG_BYTES, "p2.png")
    db_session.commit()

    # Move p2 para cima (up) -> deve trocar com p1
    moved = folders_service.move_photo_order(db_session, folder, p2.id, "up")
    db_session.commit()
    assert moved is True

    photos = folders_service.get_folder_photos(db_session, folder.id)
    assert [p.id for p in photos] == [p2.id, p1.id]
    assert [p.order for p in photos] == [0, 1]

    # Tentativa de mover p2 para cima novamente (já é a primeira)
    assert folders_service.move_photo_order(db_session, folder, p2.id, "up") is False

    for p in photos:
        storage.delete_file(p.filename)


def test_api_add_photo_auth_and_permissions(client: TestClient) -> None:
    # Anônimo tenta enviar foto
    r_anon = client.post(
        "/folders/qualquer-pasta/photos",
        files={"file": ("foto.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers={"Accept": "application/json"},
    )
    assert r_anon.status_code == 401

    # Cria usuário A e sua pasta
    client.post("/register", data={"username": "user_a", "email": "a@example.com", "password": "password123"})
    r_folder = client.post("/folders", json={"title": "Pasta A"})
    slug_a = r_folder.json()["slug"]

    # Desloga e cria usuário B
    client.post("/logout")
    client.post("/register", data={"username": "user_b", "email": "b@example.com", "password": "password123"})

    # Usuário B tenta adicionar foto na pasta do Usuário A -> 403
    r_forbidden = client.post(
        f"/folders/{slug_a}/photos",
        files={"file": ("foto.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers={"Accept": "application/json"},
    )
    assert r_forbidden.status_code == 403


def test_api_add_photo_validation_error(client: TestClient) -> None:
    client.post("/register", data={"username": "user_valid", "email": "val@example.com", "password": "password123"})
    r_folder = client.post("/folders", json={"title": "Pasta Validação"})
    slug = r_folder.json()["slug"]

    # Envia arquivo de texto em vez de imagem
    r_bad = client.post(
        f"/folders/{slug}/photos",
        files={"file": ("texto.txt", io.BytesIO(b"conteudo texto"), "text/plain")},
        headers={"Accept": "application/json"},
    )
    assert r_bad.status_code == 400
    assert "Extensão 'txt' não é permitida" in r_bad.json()["detail"] or "não é um formato de imagem suportado" in r_bad.json()["detail"] or "Extensão" in r_bad.json()["detail"]


def test_api_multi_upload_partial_failure_cleans_orphan_files(client: TestClient) -> None:
    client.post("/register", data={"username": "user_multi", "email": "multi@example.com", "password": "password123"})
    r_folder = client.post("/folders", json={"title": "Upload Multiplo"})
    slug = r_folder.json()["slug"]

    upload_dir = get_upload_dir()
    files_before = len(list(upload_dir.glob("*")))

    r_mix = client.post(
        f"/folders/{slug}/photos",
        files=[
            ("files", ("valid.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")),
            ("files", ("invalid.txt", io.BytesIO(b"texto"), "text/plain")),
        ],
        headers={"Accept": "application/json"},
    )
    assert r_mix.status_code == 400

    r_page = client.get(f"/folders/{slug}/edit")
    assert r_page.status_code == 200
    assert "Nenhuma foto nesta pasta ainda." in r_page.text
    assert len(list(upload_dir.glob("*"))) == files_before


def test_api_add_photo_success_and_delete(client: TestClient) -> None:
    client.post("/register", data={"username": "user_photo", "email": "photo@example.com", "password": "password123"})
    r_folder = client.post("/folders", json={"title": "Viagem Paris"})
    slug = r_folder.json()["slug"]

    # Upload de foto com sucesso
    r_upload = client.post(
        f"/folders/{slug}/photos",
        files={"file": ("torre.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers={"Accept": "application/json"},
    )
    assert r_upload.status_code == 201
    photo_data = r_upload.json()
    assert photo_data["id"] is not None
    assert photo_data["original_name"] == "torre.jpg"
    assert photo_data["order"] == 0
    filename = photo_data["filename"]
    assert storage.file_exists(filename) is True

    # Exclui foto
    r_del = client.delete(f"/folders/{slug}/photos/{photo_data['id']}")
    assert r_del.status_code == 200
    assert r_del.json()["status"] == "ok"
    assert storage.file_exists(filename) is False

    # Tenta excluir novamente -> 404
    r_del_again = client.delete(f"/folders/{slug}/photos/{photo_data['id']}")
    assert r_del_again.status_code == 404


def test_api_reorder_photos(client: TestClient) -> None:
    client.post("/register", data={"username": "user_reorder", "email": "reorder@example.com", "password": "password123"})
    r_folder = client.post("/folders", json={"title": "Ordem de Fotos"})
    slug = r_folder.json()["slug"]

    # Adiciona 2 fotos
    r1 = client.post(
        f"/folders/{slug}/photos",
        files={"file": ("f1.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers={"Accept": "application/json"},
    )
    r2 = client.post(
        f"/folders/{slug}/photos",
        files={"file": ("f2.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers={"Accept": "application/json"},
    )
    p1 = r1.json()
    p2 = r2.json()

    # Reordena via PUT
    r_put = client.put(
        f"/folders/{slug}/photos/order",
        json={"photo_ids": [p2["id"], p1["id"]]},
    )
    assert r_put.status_code == 200
    ordered = r_put.json()
    assert [p["id"] for p in ordered] == [p2["id"], p1["id"]]
    assert [p["order"] for p in ordered] == [0, 1]

    # Limpeza
    storage.delete_file(p1["filename"])
    storage.delete_file(p2["filename"])


def test_ssr_folder_edit_page(client: TestClient) -> None:
    # Anônimo é redirecionado para /login
    r_anon = client.get("/folders/alguma-pasta/edit", follow_redirects=False)
    assert r_anon.status_code == 303
    assert r_anon.headers["location"] == "/login"

    # Cria dono
    client.post("/register", data={"username": "owner_ssr", "email": "owner@example.com", "password": "password123"})
    r_f = client.post("/folders", json={"title": "Pasta SSR"})
    slug = r_f.json()["slug"]

    # Dono acessa página de gerenciar fotos
    r_owner = client.get(f"/folders/{slug}/edit")
    assert r_owner.status_code == 200
    assert "Gerenciar Fotos — Pasta SSR" in r_owner.text
    assert "Adicionar Fotos" in r_owner.text
    assert "Nenhuma foto nesta pasta ainda." in r_owner.text


def test_ssr_upload_delete_and_move_photos(client: TestClient) -> None:
    import re

    client.post("/register", data={"username": "ssr_user", "email": "ssr@example.com", "password": "password123"})
    r_f = client.post("/folders", json={"title": "Fluxo Completo SSR"})
    slug = r_f.json()["slug"]

    # 1. Upload de 2 fotos via formulário SSR
    r_up1 = client.post(
        f"/folders/{slug}/photos",
        files={"files": ("foto1.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        follow_redirects=False,
    )
    assert r_up1.status_code == 303
    assert r_up1.headers["location"] == f"/folders/{slug}/edit"

    r_up2 = client.post(
        f"/folders/{slug}/photos",
        files={"files": ("foto2.png", io.BytesIO(PNG_BYTES), "image/png")},
        follow_redirects=False,
    )
    assert r_up2.status_code == 303

    # 2. Verifica se a página renderiza as 2 fotos
    r_page = client.get(f"/folders/{slug}/edit")
    assert r_page.status_code == 200
    assert "foto1.jpg" in r_page.text
    assert "foto2.png" in r_page.text

    # Extrai os IDs das fotos dos actions de move
    photo_ids = [int(x) for x in re.findall(rf"/folders/{slug}/photos/(\d+)/move", r_page.text)]
    assert len(photo_ids) >= 2
    p1_id, p2_id = photo_ids[0], photo_ids[1]

    # 3. Move a segunda foto para cima
    r_move = client.post(
        f"/folders/{slug}/photos/{p2_id}/move",
        data={"direction": "up"},
        follow_redirects=False,
    )
    assert r_move.status_code == 303
    assert r_move.headers["location"] == f"/folders/{slug}/edit"

    r_page_after_move = client.get(f"/folders/{slug}/edit")
    assert "Ordem atualizada com sucesso." in r_page_after_move.text

    # 4. Remove a primeira foto via formulário SSR
    r_del = client.post(
        f"/folders/{slug}/photos/{p1_id}/delete",
        follow_redirects=False,
    )
    assert r_del.status_code == 303
    assert r_del.headers["location"] == f"/folders/{slug}/edit"

    r_page_after_del = client.get(f"/folders/{slug}/edit")
    assert "Foto removida com sucesso!" in r_page_after_del.text
    assert "foto1.jpg" not in r_page_after_del.text
    assert "foto2.png" in r_page_after_del.text


# --- Testes das Tarefas 1.8, 1.9 e 1.10: Página Pública por Slug e Feed Comunitário ---


def test_folder_detail_public_accessible_by_anyone(client: TestClient) -> None:
    client.post("/register", data={"username": "creator", "email": "c@example.com", "password": "password123"})
    r_f = client.post("/folders", json={"title": "Paisagens do Sul", "description": "Serras e praias", "is_public": True})
    slug = r_f.json()["slug"]

    # Adiciona 1 foto
    client.post(
        f"/folders/{slug}/photos",
        files={"file": ("serra.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
    )

    # 1. Dono acessa -> vê detalhes, autor, fotos e botão "Gerenciar fotos"
    r_owner = client.get(f"/folders/{slug}")
    assert r_owner.status_code == 200
    assert "Paisagens do Sul" in r_owner.text
    assert "@creator" in r_owner.text
    assert "serra.jpg" in r_owner.text
    assert "Gerenciar fotos" in r_owner.text

    # 2. Desloga e anônimo acessa -> vê detalhes e foto, mas NÃO vê "Gerenciar fotos"
    client.post("/logout")
    r_anon = client.get(f"/folders/{slug}")
    assert r_anon.status_code == 200
    assert "Paisagens do Sul" in r_anon.text
    assert "@creator" in r_anon.text
    assert "serra.jpg" in r_anon.text
    assert "Gerenciar fotos" not in r_anon.text


def test_folder_detail_private_permissions(client: TestClient) -> None:
    client.post("/register", data={"username": "secret_agent", "email": "agent@example.com", "password": "password123"})
    r_f = client.post("/folders", json={"title": "Arquivos Confidenciais", "is_public": False})
    slug = r_f.json()["slug"]

    # Dono acessa -> sucesso (200)
    r_owner = client.get(f"/folders/{slug}")
    assert r_owner.status_code == 200
    assert "Arquivos Confidenciais" in r_owner.text
    assert "Privada" in r_owner.text

    # Desloga: anônimo acessa -> 404 (para não revelar existência)
    client.post("/logout")
    r_anon = client.get(f"/folders/{slug}")
    assert r_anon.status_code == 404

    # Outro usuário autenticado acessa -> 404
    client.post("/register", data={"username": "curious_user", "email": "curious@example.com", "password": "password123"})
    r_other = client.get(f"/folders/{slug}")
    assert r_other.status_code == 404


def test_folder_detail_private_json_returns_404(client: TestClient) -> None:
    client.post("/register", data={"username": "private_api", "email": "priv@example.com", "password": "password123"})
    r_f = client.post("/folders", json={"title": "Privada API", "is_public": False})
    slug = r_f.json()["slug"]

    client.post("/logout")
    r_json = client.get(f"/folders/{slug}", headers={"Accept": "application/json"})
    assert r_json.status_code == 404


def test_folder_detail_not_found(client: TestClient) -> None:
    response = client.get("/folders/pasta-que-nao-existe")
    assert response.status_code == 404


def test_folder_detail_json_api(client: TestClient) -> None:
    client.post("/register", data={"username": "api_user", "email": "api@example.com", "password": "password123"})
    r_f = client.post("/folders", json={"title": "Pasta API", "is_public": True})
    slug = r_f.json()["slug"]

    client.post(
        f"/folders/{slug}/photos",
        files={"file": ("api_foto.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
    )

    r_json = client.get(f"/folders/{slug}", headers={"Accept": "application/json"})
    assert r_json.status_code == 200
    data = r_json.json()
    assert data["title"] == "Pasta API"
    assert data["slug"] == slug
    assert data["is_public"] is True
    assert data["owner_username"] == "api_user"
    assert len(data["photos"]) == 1
    assert data["photos"][0]["original_name"] == "api_foto.jpg"


def test_public_feed_displays_recent_folders_and_excludes_private(client: TestClient) -> None:
    client.post("/register", data={"username": "photographer", "email": "photo@test.com", "password": "password123"})

    # Cria pasta pública com foto
    r_pub1 = client.post("/folders", json={"title": "Natureza Viva", "is_public": True})
    slug_pub1 = r_pub1.json()["slug"]
    client.post(
        f"/folders/{slug_pub1}/photos",
        files={"file": ("arvore.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
    )

    # Cria pasta privada
    client.post("/folders", json={"title": "Segredos Pessoais", "is_public": False})

    # Cria outra pasta pública mais recente
    client.post("/folders", json={"title": "Arquitetura Urbana", "is_public": True})

    # Desloga para verificar como visitante no feed público
    client.post("/logout")
    r_feed = client.get("/")
    assert r_feed.status_code == 200

    # Deve exibir as pastas públicas
    assert "Natureza Viva" in r_feed.text
    assert "Arquitetura Urbana" in r_feed.text
    assert "@photographer" in r_feed.text

    # NÃO deve exibir a pasta privada
    assert "Segredos Pessoais" not in r_feed.text


def test_phase1_full_integration_flow(client: TestClient) -> None:
    # 1. Usuário cria conta
    client.post("/register", data={"username": "beatriz", "email": "beatriz@example.com", "password": "password123"})

    # 2. Cria pasta pública
    r_create = client.post(
        "/folders/new",
        data={"title": "Minha Viagem 2026", "description": "Roteiro pelo Brasil", "is_public": "true"},
        follow_redirects=False,
    )
    assert r_create.status_code == 303
    assert r_create.headers["location"] == "/me/folders"

    # 3. Listagem /me/folders
    r_my = client.get("/me/folders")
    assert r_my.status_code == 200
    assert "Minha Viagem 2026" in r_my.text

    # 4. Upload de 2 fotos
    r_up1 = client.post(
        "/folders/minha-viagem-2026/photos",
        files={"file": ("foto1.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg")},
        headers={"Accept": "application/json"},
    )
    assert r_up1.status_code == 201
    photo1 = r_up1.json()

    r_up2 = client.post(
        "/folders/minha-viagem-2026/photos",
        files={"file": ("foto2.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers={"Accept": "application/json"},
    )
    assert r_up2.status_code == 201
    photo2 = r_up2.json()

    # 5. Reordena fotos (foto2 na frente)
    r_reorder = client.put(
        "/folders/minha-viagem-2026/photos/order",
        json={"photo_ids": [photo2["id"], photo1["id"]]},
    )
    assert r_reorder.status_code == 200
    assert [p["id"] for p in r_reorder.json()] == [photo2["id"], photo1["id"]]

    # 6. Acesso à página pública por slug
    r_detail = client.get("/folders/minha-viagem-2026")
    assert r_detail.status_code == 200
    assert "Minha Viagem 2026" in r_detail.text
    assert "@beatriz" in r_detail.text
    assert "foto1.jpg" in r_detail.text
    assert "foto2.png" in r_detail.text

    # 7. Visitante anônimo vê no feed e na página pública
    client.post("/logout")
    r_feed = client.get("/")
    assert "Minha Viagem 2026" in r_feed.text
    assert "@beatriz" in r_feed.text

    r_public_view = client.get("/folders/minha-viagem-2026")
    assert r_public_view.status_code == 200
    assert "Gerenciar fotos" not in r_public_view.text

    # Limpeza de storage
    storage.delete_file(photo1["filename"])
    storage.delete_file(photo2["filename"])




