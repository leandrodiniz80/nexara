import uuid

from pydantic import BaseModel

from app.schemas.common import AuditSchema


class CompanyTagBase(BaseModel):
    company_id: uuid.UUID
    tag_id: uuid.UUID


class CompanyTagCreate(CompanyTagBase):
    pass


class CompanyTagRead(CompanyTagBase, AuditSchema):
    pass
