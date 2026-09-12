from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator


class PhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    folder_id: int
    filename: str
    original_name: str
    order: int
    created_at: datetime


class PhotoValidationInfo(BaseModel):
    canonical_extension: str
    mime_type: str
    size_bytes: int
    original_name: str


class PhotoDeleteResponse(BaseModel):
    status: str
    message: str


class PhotoOrderItem(BaseModel):
    id: int
    order: int


class PhotoReorderRequest(BaseModel):
    photo_ids: list[int] | None = None
    photos: list[PhotoOrderItem] | None = None

    @model_validator(mode="after")
    def validate_reorder_payload(self) -> "PhotoReorderRequest":
        if not self.photo_ids and not self.photos:
            raise ValueError("Informe 'photo_ids' ou 'photos' para reordenar.")
        return self

    def get_ordered_ids(self) -> list[int]:
        if self.photo_ids is not None:
            return self.photo_ids
        if self.photos is not None:
            sorted_items = sorted(self.photos, key=lambda item: item.order)
            return [item.id for item in sorted_items]
        return []

