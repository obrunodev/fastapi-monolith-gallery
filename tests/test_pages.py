from fastapi.testclient import TestClient

REGISTER_DATA = {
    "username": "alice",
    "email": "alice@example.com",
    "password": "secret123",
}


def test_feed_renders_for_visitor(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Explore fotos e coleções da comunidade" in response.text
    assert "Criar conta" in response.text
    assert "Entrar" in response.text
    assert "Nenhuma pasta pública publicada ainda." in response.text


def test_feed_renders_for_authenticated_user(client: TestClient) -> None:
    client.post("/register", data=REGISTER_DATA)
    response = client.get("/")
    assert response.status_code == 200
    assert "Explore fotos e coleções da comunidade" not in response.text
    assert "Nenhuma pasta pública publicada ainda." in response.text
    assert "alice" in response.text
    assert ">Sair<" in response.text
