from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config import get_upload_dir
from src.services import storage


def test_save_and_retrieve_file(tmp_path: Path) -> None:
    content = b"fake-image-bytes"
    filename = storage.save_file(content, ".jpg", base_dir=tmp_path)

    assert filename.endswith(".jpg")
    file_path = storage.get_file_path(filename, base_dir=tmp_path)
    assert file_path.is_file()
    assert file_path.read_bytes() == content
    assert storage.file_exists(filename, base_dir=tmp_path) is True


def test_save_file_normalizes_extension_without_dot(tmp_path: Path) -> None:
    filename = storage.save_file(b"data", "png", base_dir=tmp_path)
    assert filename.endswith(".png")


def test_save_file_rejects_invalid_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Extensão"):
        storage.save_file(b"data", "jpg/../../php", base_dir=tmp_path)


def test_delete_file_rejects_invalid_name(tmp_path: Path) -> None:
    assert storage.delete_file("../secret.txt", base_dir=tmp_path) is False


def test_delete_file(tmp_path: Path) -> None:
    filename = storage.save_file(b"to-delete", ".jpg", base_dir=tmp_path)
    assert storage.file_exists(filename, base_dir=tmp_path) is True

    deleted = storage.delete_file(filename, base_dir=tmp_path)
    assert deleted is True
    assert storage.file_exists(filename, base_dir=tmp_path) is False

    # Deletar novamente retorna False
    assert storage.delete_file(filename, base_dir=tmp_path) is False


def test_path_traversal_prevention(tmp_path: Path) -> None:
    # Nomes com ../ ou separadores devem ser rejeitados
    with pytest.raises(ValueError):
        storage.get_file_path("../secret.txt", base_dir=tmp_path)

    with pytest.raises(ValueError):
        storage.get_file_path("sub/file.jpg", base_dir=tmp_path)

    with pytest.raises(ValueError):
        storage.get_file_path("..\\windows.txt", base_dir=tmp_path)


def test_upload_dir_configurable_by_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom_dir = tmp_path / "custom_uploads"
    monkeypatch.setenv("UPLOAD_DIR", str(custom_dir))

    resolved = get_upload_dir()
    assert resolved == custom_dir.resolve()


def test_uploaded_file_is_served_via_static_mount(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Cria arquivo no diretório de uploads atual
    current_upload_dir = get_upload_dir()
    filename = storage.save_file(b"serving-test", ".txt", base_dir=current_upload_dir)

    try:
        response = client.get(f"/uploads/{filename}")
        assert response.status_code == 200
        assert response.content == b"serving-test"
    finally:
        storage.delete_file(filename, base_dir=current_upload_dir)
