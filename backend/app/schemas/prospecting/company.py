from pydantic import BaseModel, EmailStr, Field

from app.models.prospecting.enums import RevenueRange
from app.schemas.common import AuditSchema


class CompanyBase(BaseModel):
    legal_name: str = Field(..., max_length=255)
    trade_name: str | None = Field(None, max_length=255)
    cnpj: str = Field(..., min_length=14, max_length=14, pattern=r"^\d{14}$")
    segment: str | None = Field(None, max_length=120)
    cnae: str | None = Field(None, max_length=10)
    website: str | None = Field(None, max_length=255)
    instagram: str | None = Field(None, max_length=255)
    linkedin: str | None = Field(None, max_length=255)
    primary_phone: str | None = Field(None, max_length=20)
    primary_email: EmailStr | None = None
    city: str | None = Field(None, max_length=120)
    state: str | None = Field(None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    zip_code: str | None = Field(None, max_length=9)
    employees_count_estimate: int | None = Field(None, ge=0)
    revenue_range_estimate: RevenueRange | None = None
    notes: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    legal_name: str | None = Field(None, max_length=255)
    trade_name: str | None = Field(None, max_length=255)
    cnpj: str | None = Field(None, min_length=14, max_length=14, pattern=r"^\d{14}$")
    segment: str | None = Field(None, max_length=120)
    cnae: str | None = Field(None, max_length=10)
    website: str | None = Field(None, max_length=255)
    instagram: str | None = Field(None, max_length=255)
    linkedin: str | None = Field(None, max_length=255)
    primary_phone: str | None = Field(None, max_length=20)
    primary_email: EmailStr | None = None
    city: str | None = Field(None, max_length=120)
    state: str | None = Field(None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    zip_code: str | None = Field(None, max_length=9)
    employees_count_estimate: int | None = Field(None, ge=0)
    revenue_range_estimate: RevenueRange | None = None
    notes: str | None = None


class CompanyRead(CompanyBase, AuditSchema):
    pass
