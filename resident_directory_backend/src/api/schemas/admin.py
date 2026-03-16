import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.api.schemas.residents import PrivacySettings


class ImportResidentRow(BaseModel):
    email: str = Field(..., description="Resident email")
    password: str = Field(..., description="Initial password (will be hashed)")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    display_name: str | None = Field(None, description="Display name")
    unit: str | None = Field(None, description="Unit")
    building: str | None = Field(None, description="Building")
    phone: str | None = Field(None, description="Phone")
    bio: str | None = Field(None, description="Bio")
    tags: list[str] = Field(default_factory=list, description="Tags")
    privacy: PrivacySettings | None = Field(None, description="Optional privacy override")


class ImportRequest(BaseModel):
    residents: list[ImportResidentRow] = Field(..., description="Residents to import")


class ImportJobOut(BaseModel):
    id: uuid.UUID = Field(..., description="Import job id")
    status: str = Field(..., description="queued|running|succeeded|failed|cancelled")
    total_records: int = Field(..., description="Total rows")
    processed_records: int = Field(..., description="Processed rows")
    error_count: int = Field(..., description="Errors")
    error_summary: str | None = Field(None, description="Error summary")
    created_at: datetime = Field(..., description="Created timestamp")
    started_at: datetime | None = Field(None, description="Started timestamp")
    finished_at: datetime | None = Field(None, description="Finished timestamp")


class ExportRequest(BaseModel):
    format: str = Field("csv", description="csv|json")


class ExportJobOut(BaseModel):
    id: uuid.UUID = Field(..., description="Export job id")
    format: str = Field(..., description="csv|json")
    status: str = Field(..., description="queued|running|succeeded|failed|cancelled")
    total_records: int = Field(..., description="Total rows exported")
    created_at: datetime = Field(..., description="Created timestamp")
    started_at: datetime | None = Field(None, description="Started timestamp")
    finished_at: datetime | None = Field(None, description="Finished timestamp")
    error_summary: str | None = Field(None, description="Error summary")


class AuditLogOut(BaseModel):
    id: uuid.UUID = Field(..., description="Audit log id")
    actor_user_id: uuid.UUID | None = Field(None, description="Actor user id")
    action: str = Field(..., description="Action key")
    entity_type: str | None = Field(None, description="Entity type")
    entity_id: uuid.UUID | None = Field(None, description="Entity id")
    success: bool = Field(..., description="Success flag")
    details: dict = Field(..., description="Details JSON")
    created_at: datetime = Field(..., description="Created timestamp")
