import uuid

from app.crm.models.crm_company import CRMCompany
from app.crm.repositories.company_repository import CompanyRepository


def test_save_and_get_company_round_trip():
    repository = CompanyRepository()
    company = CRMCompany(name="Agência XYZ")

    repository.save_company(company)

    assert repository.get_company(company.id) is company


def test_get_company_for_unknown_id_returns_none():
    repository = CompanyRepository()

    assert repository.get_company(uuid.uuid4()) is None


def test_save_company_overwrites_the_same_id_in_place():
    repository = CompanyRepository()
    company = CRMCompany(name="Agência XYZ")
    repository.save_company(company)

    company.segment = "Publicidade"
    repository.save_company(company)

    assert repository.get_company(company.id).segment == "Publicidade"


def test_list_companies_returns_every_saved_company():
    repository = CompanyRepository()
    first = CRMCompany(name="Agência XYZ")
    second = CRMCompany(name="Outdoor Prime")
    repository.save_company(first)
    repository.save_company(second)

    companies = repository.list_companies()

    assert {c.id for c in companies} == {first.id, second.id}
