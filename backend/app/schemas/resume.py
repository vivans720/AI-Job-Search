import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict


class ResumeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    resume_hash: str
    is_active: bool
    created_at: datetime
    extracted_data: dict[str, Any]
