import re
import uuid
from pathlib import Path

from src.config import get_upload_dir

# Apenas caracteres alfanuméricos, underscore, hífen e um único ponto para extensão
SAFE_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+\.[a-zA-Z0-9]+$")


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
