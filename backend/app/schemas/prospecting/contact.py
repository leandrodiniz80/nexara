import uuid

from pydantic import BaseModel, EmailStr, Field

from app.models.prospecting.enums import ContactStatus
from app.schemas.common import AuditSchema


class ContactBase(BaseModel):
    company_id: uuid.UUID
    full_name: str = Field(..., max_length=255)
    job_title: str | None = Field(None, max_length=120)
    department: str | None = Field(None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    whatsapp: str | None = Field(None, max_length=20)
    linkedin: str | None = Field(None, max_length=255)
    is_decision_maker: bool = False
    status: ContactStatus = ContactStatus.ACTIVE


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    company_id: uuid.UUID | None = None
    full_name: str | None = Field(None, max_length=255)
    job_title: str | None = Field(None, max_length=120)
    department: str | None = Field(None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    whatsapp: str | None = Field(None, max_length=20)
    linkedin: str | None = Field(None, max_length=255)
    is_decision_maker: bool | None = None
    status: ContactStatus | None = None


class ContactRead(ContactBase, AuditSchema):
    pass
