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

