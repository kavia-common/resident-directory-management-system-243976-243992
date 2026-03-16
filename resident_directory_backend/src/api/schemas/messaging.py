import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ContactRequestCreate(BaseModel):
    to_user_id: uuid.UUID = Field(..., description="Recipient user id")
    subject: str | None = Field(None, description="Optional subject")
    initial_message: str = Field(..., min_length=1, description="Initial message body")


class ContactRequestOut(BaseModel):
    id: uuid.UUID = Field(..., description="Contact request id")
    from_user_id: uuid.UUID = Field(..., description="Sender user id")
    to_user_id: uuid.UUID = Field(..., description="Recipient user id")
    subject: str | None = Field(None, description="Subject")
    initial_message: str = Field(..., description="Initial message")
    status: str = Field(..., description="pending|accepted|declined|cancelled|closed")
    responded_at: datetime | None = Field(None, description="When responded")
    created_at: datetime = Field(..., description="Created timestamp")
    updated_at: datetime = Field(..., description="Updated timestamp")


class ContactRequestRespond(BaseModel):
    action: str = Field(..., description="accepted|declined|closed")


class MessageThreadOut(BaseModel):
    id: uuid.UUID = Field(..., description="Thread id")
    contact_request_id: uuid.UUID | None = Field(None, description="Associated contact request")
    created_at: datetime = Field(..., description="Created timestamp")
    participants: list[uuid.UUID] = Field(default_factory=list, description="Participant user ids")


class MessageCreate(BaseModel):
    body: str = Field(..., min_length=1, description="Message body")


class MessageOut(BaseModel):
    id: uuid.UUID = Field(..., description="Message id")
    thread_id: uuid.UUID = Field(..., description="Thread id")
    sender_user_id: uuid.UUID | None = Field(None, description="Sender user id")
    body: str = Field(..., description="Body")
    created_at: datetime = Field(..., description="Created timestamp")
