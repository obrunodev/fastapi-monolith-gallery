import re
import uuid
from pathlib import Path

from src.config import get_max_upload_size, get_upload_dir
from src.schemas.photo import PhotoValidationInfo

# Apenas caracteres alfanuméricos, underscore, hífen e um único ponto para extensão
SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+$")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

EXTENSION_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

MIME_TO_CANONICAL_EXT = {
    "image/jpeg": ".jpg",
    "image/pjpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class StorageValidationError(ValueError):
    """Exceção levantada quando um upload de arquivo falha nas validações de segurança/formato."""

    pass


def detect_image_format(content: bytes) -> str | None:
    """Identifica o formato da imagem com base nos magic bytes (assinatura binária).

    Retorna a extensão canônica ('.jpg', '.png', '.webp', '.gif') ou None se não for suportado.
    """
    if len(content) >= 3 and content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(content) >= 8 and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(content) >= 6 and (content.startswith(b"GIF87a") or content.startswith(b"GIF89a")):
        return ".gif"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    return None


def validate_image(
    content: bytes,
    original_filename: str | None = None,
    content_type: str | None = None,
    max_size: int | None = None,
) -> PhotoValidationInfo:
    """Valida conteúdo, tamanho, extensão e MIME type de um upload de imagem.

    Args:
        content: Conteúdo binário do arquivo.
        original_filename: Nome original do arquivo enviado pelo cliente.
        content_type: Tipo MIME informado pelo cliente (ex: 'image/jpeg').
        max_size: Limite de tamanho em bytes (se None, usa get_max_upload_size()).

    Returns:
        PhotoValidationInfo com extensão canônica, mime type, tamanho e nome limpo.

    Raises:
        StorageValidationError: Se qualquer validação falhar.
    """
    if not content:
        raise StorageValidationError("O arquivo enviado está vazio.")

    max_allowed = max_size if max_size is not None else get_max_upload_size()
    if len(content) > max_allowed:
        raise StorageValidationError(
            f"O arquivo excede o limite máximo permitido de {max_allowed} bytes."
        )

    detected_ext = detect_image_format(content)
    if detected_ext is None:
        raise StorageValidationError(
            "O conteúdo do arquivo não é um formato de imagem suportado (permitidos: JPG, PNG, WEBP, GIF)."
        )

    detected_mime = EXTENSION_TO_MIME[detected_ext]

    clean_original_name: str
    if original_filename:
        clean_original_name = Path(original_filename).name.strip()
        if not clean_original_name:
            raise StorageValidationError("Nome de arquivo original inválido.")

        declared_ext = Path(clean_original_name).suffix.lower()
        if declared_ext not in ALLOWED_IMAGE_EXTENSIONS:
            allowed_str = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
            raise StorageValidationError(
                f"Extensão '{declared_ext}' não é permitida. Extensões válidas: {allowed_str}"
            )

        is_jpeg_match = detected_ext == ".jpg" and declared_ext in {".jpg", ".jpeg"}
        if not is_jpeg_match and declared_ext != detected_ext:
            raise StorageValidationError(
                f"A extensão declarada '{declared_ext}' não corresponde ao formato real do arquivo ('{detected_ext}')."
            )
    else:
        clean_original_name = f"image{detected_ext}"

    if content_type:
        clean_mime = content_type.lower().split(";")[0].strip()
        if clean_mime not in MIME_TO_CANONICAL_EXT:
            raise StorageValidationError(f"Tipo MIME não suportado: '{content_type}'.")

        expected_ext = MIME_TO_CANONICAL_EXT[clean_mime]
        if expected_ext != detected_ext:
            raise StorageValidationError(
                f"O tipo MIME '{content_type}' não corresponde ao formato real do arquivo ('{detected_ext}')."
            )

    return PhotoValidationInfo(
        canonical_extension=detected_ext,
        mime_type=detected_mime,
        size_bytes=len(content),
        original_name=clean_original_name,
    )


def ensure_upload_dir(base_dir: Path | None = None) -> Path:
    """Garante que o diretório de uploads existe e retorna o Path resolvido."""
    target_dir = (base_dir or get_upload_dir()).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _validate_filename(filename: str, base_dir: Path) -> Path:
    """Valida o nome do arquivo contra directory traversal e caracteres perigosos."""
    if not filename or not SAFE_FILENAME_REGEX.match(filename):
        raise ValueError(f"Nome de arquivo inválido: '{filename}'")

    target_path = (base_dir / filename).resolve()
    # Garante que o arquivo está estritamente dentro de base_dir
    try:
        target_path.relative_to(base_dir)
    except ValueError:
        raise ValueError(f"Tentativa de path traversal detectada: '{filename}'")

    return target_path


def save_file(
    content: bytes,
    extension: str,
    base_dir: Path | None = None,
) -> str:
    """Salva o conteúdo em disco com um nome único gerado e retorna o filename.

    Args:
        content: Conteúdo binário do arquivo.
        extension: Extensão desejada (ex: '.jpg' ou 'jpg').
        base_dir: Diretório de destino opcional (default: get_upload_dir()).

    Returns:
        O nome do arquivo gerado (ex: '3f2b4c1...jpg').
    """
    ext = extension.strip().lower()
    if not ext.startswith("."):
        ext = f".{ext}"

    if not re.match(r"^\.[a-z0-9]+$", ext):
        raise ValueError(f"Extensão de arquivo inválida: '{extension}'")

    target_dir = ensure_upload_dir(base_dir)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    target_path = _validate_filename(unique_name, target_dir)

    target_path.write_bytes(content)
    return unique_name


def get_file_path(filename: str, base_dir: Path | None = None) -> Path:
    """Retorna o Path do arquivo após validar contra path traversal."""
    target_dir = (base_dir or get_upload_dir()).resolve()
    return _validate_filename(filename, target_dir)


def file_exists(filename: str, base_dir: Path | None = None) -> bool:
    """Verifica se o arquivo existe dentro do diretório de uploads."""
    try:
        target_path = get_file_path(filename, base_dir)
        return target_path.is_file()
    except ValueError:
        return False


def delete_file(filename: str, base_dir: Path | None = None) -> bool:
    """Remove o arquivo do disco com segurança.

    Returns:
        True se o arquivo existia e foi removido; False se não existia ou o nome é inválido.
    """
    try:
        target_path = get_file_path(filename, base_dir)
    except ValueError:
        return False

    if target_path.is_file():
        target_path.unlink()
        return True
    return False


def save_image(
    content: bytes,
    original_filename: str | None = None,
    content_type: str | None = None,
    base_dir: Path | None = None,
    max_size: int | None = None,
) -> tuple[str, PhotoValidationInfo]:
    """Valida a imagem e a salva com nome único no disco.

    Args:
        content: Conteúdo binário da imagem.
        original_filename: Nome original do arquivo.
        content_type: Header Content-Type opcional.
        base_dir: Diretório de destino customizado (opcional).
        max_size: Limite de tamanho customizado (opcional).

    Returns:
        Tupla com (nome_do_arquivo_salvo, PhotoValidationInfo).
    """
    validated = validate_image(
        content=content,
        original_filename=original_filename,
        content_type=content_type,
        max_size=max_size,
    )
    saved_filename = save_file(
        content=content,
        extension=validated.canonical_extension,
        base_dir=base_dir,
    )
    return saved_filename, validated

