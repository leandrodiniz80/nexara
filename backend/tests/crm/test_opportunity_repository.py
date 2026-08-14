import uuid

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.repositories.opportunity_repository import OpportunityRepository


def _opportunity(**overrides) -> CRMOpportunity:
    defaults = dict(
        company_id=uuid.uuid4(),
        title="Outdoor Digital",
        pipeline_id=uuid.uuid4(),
        stage_id=uuid.uuid4(),
    )
    defaults.update(overrides)
    return CRMOpportunity(**defaults)


def test_save_and_get_opportunity_round_trip():
    repository = OpportunityRepository()
    opportunity = _opportunity()

    repository.save_opportunity(opportunity)

    assert repository.get_opportunity(opportunity.id) is opportunity


def test_get_opportunity_for_unknown_id_returns_none():
    repository = OpportunityRepository()

    assert repository.get_opportunity(uuid.uuid4()) is None


def test_list_opportunities_returns_every_saved_opportunity_by_default():
    repository = OpportunityRepository()
    first = _opportunity()
    second = _opportunity()
    repository.save_opportunity(first)
    repository.save_opportunity(second)

    opportunities = repository.list_opportunities()

    assert {o.id for o in opportunities} == {first.id, second.id}


def test_list_opportunities_filters_by_company_id():
    company_id = uuid.uuid4()
    repository = OpportunityRepository()
    matching = _opportunity(company_id=company_id)
    other = _opportunity()
    repository.save_opportunity(matching)
    repository.save_opportunity(other)

    opportunities = repository.list_opportunities(company_id=company_id)

    assert [o.id for o in opportunities] == [matching.id]
