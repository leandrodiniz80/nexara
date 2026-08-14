import uuid

from app.crm.models.crm_company import CRMCompany


class CompanyRepository:
    """In-memory store of every CRMCompany — no database, no migration was
    requested for this module."""

    def __init__(self) -> None:
        self._companies: dict[uuid.UUID, CRMCompany] = {}

    def save_company(self, company: CRMCompany) -> CRMCompany:
        self._companies[company.id] = company
        return company

    def get_company(self, company_id: uuid.UUID) -> CRMCompany | None:
        return self._companies.get(company_id)

    def list_companies(self) -> list[CRMCompany]:
        return list(self._companies.values())
