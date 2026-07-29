import pytest

from app.research.models.enums import ResearchSource
from app.research.providers.base.provider_base import ProviderBase
from app.research.providers.google_maps_provider import GoogleMapsProvider
from app.research.schemas.company_search_query import CompanySearchQuery


def test_provider_base_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ProviderBase()


def test_concrete_provider_exposes_its_source():
    provider = GoogleMapsProvider()
    assert provider.source == ResearchSource.GOOGLE_MAPS


async def test_stub_provider_methods_raise_not_implemented():
    provider = GoogleMapsProvider()

    with pytest.raises(NotImplementedError):
        await provider.search(CompanySearchQuery(city="Goiânia"))
    with pytest.raises(NotImplementedError):
        await provider.get_company("some-id")
    with pytest.raises(NotImplementedError):
        await provider.search_contacts(None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        await provider.health_check()
