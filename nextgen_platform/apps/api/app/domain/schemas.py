from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "admin"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    tenant_name: str = Field(min_length=2, max_length=120)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PatientCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    document_number: str = Field(min_length=3, max_length=40)


class PatientsBulkCreate(BaseModel):
    items: list[PatientCreate] = Field(min_length=1, max_length=200)


class PatientOut(BaseModel):
    id: UUID
    tenant_id: UUID
    full_name: str
    document_number: str
    created_at: datetime

    class Config:
        from_attributes = True


class VisitCreate(BaseModel):
    patient_id: UUID
    notes: str = Field(default="", max_length=5000)


class VisitsBulkCreate(BaseModel):
    items: list[VisitCreate] = Field(min_length=1, max_length=200)


class VisitOut(BaseModel):
    id: UUID
    tenant_id: UUID
    patient_id: UUID
    notes: str
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ResilienceSwitchRequest(BaseModel):
    rate_limit_fail_open: bool | None = None
    idempotency_fail_open: bool | None = None
    token_revocation_fail_open: bool | None = None
    ttl_seconds: int = Field(default=1800, ge=30, le=86400)
    reason: str = Field(min_length=8, max_length=500)
    change_ticket: str | None = Field(default=None, max_length=64)
