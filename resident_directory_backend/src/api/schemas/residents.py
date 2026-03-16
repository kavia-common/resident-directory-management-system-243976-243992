import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PrivacySettings(BaseModel):
    is_directory_visible: bool = Field(..., description="Whether profile is listed in directory")
    show_email: bool = Field(..., description="Whether email is visible to other residents")
    show_phone: bool = Field(..., description="Whether phone is visible to other residents")
    show_unit: bool = Field(..., description="Whether unit is visible to other residents")
    show_building: bool = Field(..., description="Whether building is visible to other residents")
    show_bio: bool = Field(..., description="Whether bio is visible to other residents")
    show_tags: bool = Field(..., description="Whether tags are visible to other residents")


class ResidentProfileBase(BaseModel):
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    display_name: str | None = Field(None, description="Display name")
    unit: str | None = Field(None, description="Unit/apartment number")
    building: str | None = Field(None, description="Building identifier")
    phone: str | None = Field(None, description="Phone number")
    email_public_override: str | None = Field(None, description="Optional public-facing email")
    bio: str | None = Field(None, description="Bio")
    tags: list[str] = Field(default_factory=list, description="Search/filter tags")


class ResidentProfileCreate(ResidentProfileBase):
    user_id: uuid.UUID = Field(..., description="User id to bind the profile to")
    privacy: PrivacySettings = Field(..., description="Privacy settings")


class ResidentProfileUpdate(BaseModel):
    first_name: str | None = Field(None, description="First name")
    last_name: str | None = Field(None, description="Last name")
    display_name: str | None = Field(None, description="Display name")
    unit: str | None = Field(None, description="Unit/apartment number")
    building: str | None = Field(None, description="Building identifier")
    phone: str | None = Field(None, description="Phone number")
    email_public_override: str | None = Field(None, description="Optional public-facing email")
    bio: str | None = Field(None, description="Bio")
    tags: list[str] | None = Field(None, description="Search/filter tags")


class PrivacyUpdate(PrivacySettings):
    pass


class ResidentProfileAdminView(ResidentProfileBase):
    id: uuid.UUID = Field(..., description="Profile id")
    user_id: uuid.UUID = Field(..., description="Owner user id")
    privacy: PrivacySettings = Field(..., description="Privacy settings")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")


class ResidentDirectoryCard(BaseModel):
    """Directory response projection with privacy filtering applied."""

    id: uuid.UUID = Field(..., description="Profile id")
    display_name: str = Field(..., description="Name displayed in directory")
    unit: str | None = Field(None, description="Unit if allowed")
    building: str | None = Field(None, description="Building if allowed")
    email: str | None = Field(None, description="Email if allowed")
    phone: str | None = Field(None, description="Phone if allowed")
    bio: str | None = Field(None, description="Bio if allowed")
    tags: list[str] = Field(default_factory=list, description="Tags if allowed")
