import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DATABASE_URL = f"sqlite:///{DATA_DIR / 'app.db'}"


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "admin")


def get_admin_email() -> str:
    return os.getenv("ADMIN_EMAIL", "admin@localhost")


def get_admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "admin")


def get_session_secret() -> str:
    return os.getenv("SESSION_SECRET", "dev-insecure-change-me")


UPLOAD_DIR = ROOT_DIR / "uploads"


def get_upload_dir() -> Path:
    env_dir = os.getenv("UPLOAD_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return UPLOAD_DIR


DEFAULT_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def get_max_upload_size() -> int:
    env_size = os.getenv("MAX_UPLOAD_SIZE")
    if env_size:
        try:
            val = int(env_size)
            if val > 0:
                return val
        except ValueError:
            pass
    return DEFAULT_MAX_UPLOAD_SIZE


