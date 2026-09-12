from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FolderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    is_public: bool = True
    is_adult: bool = False

    @field_validator("title", mode="before")
    @classmethod
    def validate_title(cls, value: str) -> str:
        s = str(value).strip()
        if not s:
            raise ValueError("O título da pasta não pode ser vazio.")
        if len(s) > 100:
            raise ValueError("O título não pode ter mais de 100 caracteres.")
        return s

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s if s else None


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: str | None
    owner_id: int
    is_public: bool
    is_adult: bool
    created_at: datetime
