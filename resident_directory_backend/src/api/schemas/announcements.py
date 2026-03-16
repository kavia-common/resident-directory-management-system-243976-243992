import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, description="Announcement title")
    body: str = Field(..., min_length=1, description="Announcement body")
    is_published: bool = Field(True, description="Whether announcement is published immediately")


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(None, description="Announcement title")
    body: str | None = Field(None, description="Announcement body")
    is_published: bool | None = Field(None, description="Whether published")


class AnnouncementOut(BaseModel):
    id: uuid.UUID = Field(..., description="Announcement id")
    title: str = Field(..., description="Title")
    body: str = Field(..., description="Body")
    created_by_user_id: uuid.UUID | None = Field(None, description="Creator user id")
    is_published: bool = Field(..., description="Published flag")
    published_at: datetime | None = Field(None, description="Published timestamp")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")
