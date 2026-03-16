from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email (unique, case-insensitive)")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    first_name: str = Field(..., min_length=1, description="Resident first name")
    last_name: str = Field(..., min_length=1, description="Resident last name")
    display_name: str | None = Field(None, description="Optional display name shown in directory")
