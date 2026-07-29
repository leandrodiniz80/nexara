from pydantic import BaseModel, Field

from app.schemas.common import AuditSchema


class EmailTemplateBase(BaseModel):
    name: str = Field(..., max_length=255)
    subject: str = Field(..., max_length=255)
    content_html: str
    content_text: str | None = None
    category: str | None = Field(None, max_length=100)
    version: int = Field(1, ge=1)
    is_active: bool = True


class EmailTemplateCreate(EmailTemplateBase):
    pass


class EmailTemplateUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    subject: str | None = Field(None, max_length=255)
    content_html: str | None = None
    content_text: str | None = None
    category: str | None = Field(None, max_length=100)
    version: int | None = Field(None, ge=1)
    is_active: bool | None = None


class EmailTemplateRead(EmailTemplateBase, AuditSchema):
    pass
