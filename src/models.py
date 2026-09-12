"""Modelos SQLAlchemy.

Importe novos modelos neste módulo para que o Alembic os detecte nas migrations.
"""

from src.db import Base

__all__ = ["Base"]
