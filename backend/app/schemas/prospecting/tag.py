from pydantic import BaseModel, Field

from app.schemas.common import AuditSchema


class TagBase(BaseModel):
    name: str = Field(..., max_length=80)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str | None = None


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = Field(None, max_length=80)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str | None = None


class TagRead(TagBase, AuditSchema):
    pass
