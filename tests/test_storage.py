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


# --- Testes da Tarefa 1.4: Upload com validação (tipo, tamanho, extensão) ---

JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00fakejpegdata"
PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01fake"
GIF_BYTES = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!fake"
WEBP_BYTES = b"RIFF\x20\x00\x00\x00WEBPVP8 \x14\x00\x00\x00fake"


@pytest.mark.parametrize(
    "content,filename,content_type,expected_ext,expected_mime",
    [
        (JPEG_BYTES, "photo.jpg", "image/jpeg", ".jpg", "image/jpeg"),
        (JPEG_BYTES, "photo.jpeg", "image/jpeg", ".jpg", "image/jpeg"),
        (JPEG_BYTES, "PHOTO.JPG", "image/jpeg", ".jpg", "image/jpeg"),
        (JPEG_BYTES, "photo.jpeg", "image/pjpeg", ".jpg", "image/jpeg"),
        (PNG_BYTES, "avatar.png", "image/png", ".png", "image/png"),
        (PNG_BYTES, "IMAGE.PNG", "image/png", ".png", "image/png"),
        (GIF_BYTES, "anim.gif", "image/gif", ".gif", "image/gif"),
        (WEBP_BYTES, "modern.webp", "image/webp", ".webp", "image/webp"),
    ],
)
def test_validate_image_success(
    content: bytes,
    filename: str,
    content_type: str,
    expected_ext: str,
    expected_mime: str,
) -> None:
    info = storage.validate_image(
        content=content,
        original_filename=filename,
        content_type=content_type,
    )

    assert info.canonical_extension == expected_ext
    assert info.mime_type == expected_mime
    assert info.size_bytes == len(content)
    assert info.original_name == Path(filename).name.strip()


def test_validate_image_without_original_name_and_mime() -> None:
    info = storage.validate_image(content=PNG_BYTES)

    assert info.canonical_extension == ".png"
    assert info.mime_type == "image/png"
    assert info.size_bytes == len(PNG_BYTES)
    assert info.original_name == "image.png"


def test_validate_image_sanitizes_original_name() -> None:
    info = storage.validate_image(
        content=PNG_BYTES,
        original_filename="../../etc/passwd.png",
        content_type="image/png",
    )
    assert info.original_name == "passwd.png"


def test_validate_image_rejects_empty_content() -> None:
    with pytest.raises(storage.StorageValidationError, match="vazio"):
        storage.validate_image(content=b"", original_filename="empty.jpg")


def test_validate_image_rejects_exceeding_max_size() -> None:
    # Teste com limite customizado via parâmetro
    with pytest.raises(storage.StorageValidationError, match="limite máximo"):
        storage.validate_image(
            content=JPEG_BYTES,
            original_filename="large.jpg",
            max_size=len(JPEG_BYTES) - 1,
        )


def test_validate_image_respects_max_size_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "10")
    with pytest.raises(storage.StorageValidationError, match="limite máximo"):
        storage.validate_image(content=JPEG_BYTES, original_filename="large.jpg")


def test_validate_image_rejects_unsupported_extensions() -> None:
    for bad_name in ["script.php", "doc.pdf", "app.exe", "vector.svg", "noext"]:
        with pytest.raises(storage.StorageValidationError):
            storage.validate_image(
                content=JPEG_BYTES,
                original_filename=bad_name,
            )


def test_validate_image_rejects_corrupted_or_non_image_binary() -> None:
    fake_text = b"This is plain text pretending to be an image"
    with pytest.raises(storage.StorageValidationError, match="formato de imagem suportado"):
        storage.validate_image(
            content=fake_text,
            original_filename="fake.jpg",
            content_type="image/jpeg",
        )


def test_validate_image_detects_extension_mismatch() -> None:
    # Arquivo com bytes PNG mas extensão .jpg
    with pytest.raises(storage.StorageValidationError, match="não corresponde ao formato real"):
        storage.validate_image(
            content=PNG_BYTES,
            original_filename="fake.jpg",
            content_type="image/png",
        )


def test_validate_image_detects_mime_type_mismatch() -> None:
    # Arquivo PNG real com Content-Type declarado como JPEG
    with pytest.raises(storage.StorageValidationError, match="não corresponde ao formato real"):
        storage.validate_image(
            content=PNG_BYTES,
            original_filename="image.png",
            content_type="image/jpeg",
        )


def test_validate_image_rejects_unsupported_mime() -> None:
    with pytest.raises(storage.StorageValidationError, match="Tipo MIME não suportado"):
        storage.validate_image(
            content=PNG_BYTES,
            original_filename="image.png",
            content_type="application/pdf",
        )


def test_save_image_success(tmp_path: Path) -> None:
    saved_filename, info = storage.save_image(
        content=JPEG_BYTES,
        original_filename="../sub/minha foto de férias.jpg",
        content_type="image/jpeg",
        base_dir=tmp_path,
    )

    assert saved_filename.endswith(".jpg")
    assert info.canonical_extension == ".jpg"
    assert info.mime_type == "image/jpeg"
    assert info.original_name == "minha foto de férias.jpg"
    assert info.size_bytes == len(JPEG_BYTES)

    saved_path = storage.get_file_path(saved_filename, base_dir=tmp_path)
    assert saved_path.is_file()
    assert saved_path.read_bytes() == JPEG_BYTES


def test_save_image_does_not_create_file_on_validation_failure(tmp_path: Path) -> None:
    invalid_content = b"not-an-image"
    with pytest.raises(storage.StorageValidationError):
        storage.save_image(
            content=invalid_content,
            original_filename="test.jpg",
            base_dir=tmp_path,
        )

    # Verifica que nenhum arquivo foi criado em tmp_path
    assert list(tmp_path.iterdir()) == []

