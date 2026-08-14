import uuid

import pytest
from pydantic import ValidationError

from app.crm.models.crm_company import CRMCompany
from app.crm.models.crm_contact import CRMContact
from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.sales_playbook import SalesPlaybook
from app.crm.services.sales_playbook_service import SalesPlaybookService
from app.crm.services.sales_playbook_service_factory import (
    build_default_sales_playbook_service,
)


def _company(*, segment: str | None) -> CRMCompany:
    return CRMCompany(name="Empresa Teste", segment=segment)


def _opportunity(company: CRMCompany) -> CRMOpportunity:
    return CRMOpportunity(
        company_id=company.id,
        title="Outdoor Digital",
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
    )


def _contact(company: CRMCompany) -> CRMContact:
    return CRMContact(company_id=company.id, name="Contato Teste")


def test_segmento_publicidade_recommends_the_standard_commercial_cadence():
    service = SalesPlaybookService()
    company = _company(segment="Publicidade")

    playbook = service.recommend_playbook(_opportunity(company), company)

    assert playbook.cadence_name == "Cadência Comercial Padrão"
    assert playbook.target_segment == "Publicidade"


def test_segmento_pet_recommends_the_consultative_cadence():
    service = SalesPlaybookService()
    company = _company(segment="Pet")

    playbook = service.recommend_playbook(_opportunity(company), company)

    assert playbook.cadence_name == "Cadência Consultiva"
    assert playbook.target_segment == "Pet"


def test_segmento_saude_recommends_the_institutional_cadence():
    service = SalesPlaybookService()
    company = _company(segment="Saúde")

    playbook = service.recommend_playbook(_opportunity(company), company)

    assert playbook.cadence_name == "Cadência Institucional"
    assert playbook.target_segment == "Saúde"


def test_segmento_industria_recommends_the_technical_cadence():
    service = SalesPlaybookService()
    company = _company(segment="Indústria")

    playbook = service.recommend_playbook(_opportunity(company), company)

    assert playbook.cadence_name == "Cadência Técnica"
    assert playbook.target_segment == "Indústria"


def test_segmento_desconhecido_falls_back_to_the_standard_commercial_cadence():
    service = SalesPlaybookService()
    company = _company(segment="Agropecuária")

    playbook = service.recommend_playbook(_opportunity(company), company)

    assert playbook.cadence_name == "Cadência Comercial Padrão"
    assert playbook.target_segment == "Geral"


def test_empresa_sem_segmento_falls_back_to_the_standard_commercial_cadence():
    service = SalesPlaybookService()
    company = _company(segment=None)

    playbook = service.recommend_playbook(_opportunity(company), company)

    assert playbook.cadence_name == "Cadência Comercial Padrão"
    assert playbook.target_segment == "Geral"


def test_contact_opcional_works_both_with_and_without_a_contact():
    service = SalesPlaybookService()
    company = _company(segment="Pet")
    opportunity = _opportunity(company)

    without_contact = service.recommend_playbook(opportunity, company)
    with_contact = service.recommend_playbook(opportunity, company, _contact(company))

    assert without_contact == with_contact


def test_metadata_preservado_is_carried_through_unchanged():
    service = SalesPlaybookService()
    company = _company(segment="Saúde")
    metadata = {"source": "unit-test", "campaign": "q1"}

    playbook = service.recommend_playbook(
        _opportunity(company), company, metadata=metadata
    )

    assert playbook.metadata == metadata


def test_metadata_defaults_to_an_empty_dict_when_not_provided():
    service = SalesPlaybookService()
    company = _company(segment="Publicidade")

    playbook = service.recommend_playbook(_opportunity(company), company)

    assert playbook.metadata == {}


def test_imutabilidade_do_playbook_rejects_attribute_assignment():
    service = SalesPlaybookService()
    company = _company(segment="Publicidade")

    playbook = service.recommend_playbook(_opportunity(company), company)

    with pytest.raises(ValidationError):
        playbook.priority = "BAIXA"


def test_build_default_sales_playbook_service_returns_a_usable_service():
    service = build_default_sales_playbook_service()
    company = _company(segment="Indústria")

    assert isinstance(service, SalesPlaybookService)
    playbook = service.recommend_playbook(_opportunity(company), company)
    assert isinstance(playbook, SalesPlaybook)
    assert playbook.cadence_name == "Cadência Técnica"
