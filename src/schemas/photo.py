from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
