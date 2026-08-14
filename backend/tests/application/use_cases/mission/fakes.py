import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from app.models.prospecting.campaign import Campaign
from app.models.prospecting.company import Company
from app.models.prospecting.interaction import Interaction
from app.models.prospecting.prospect import Prospect

# Same "transient SQLAlchemy instance, stamped by hand" idiom as tests/mission/fakes.py
# — these fakes let MissionEngine/ProspectEngine (both real, unmodified, SQLAlchemy-
# backed modules) run against plain in-memory dicts instead of a live Postgres, which
# this sandbox has no way to provide.


def _stamp(instance: Any, **attrs: Any) -> None:
    instance.id = uuid.uuid4()
    instance.created_at = attrs.pop("created_at", datetime.now(timezone.utc))
    instance.updated_at = instance.created_at
    for key, value in attrs.items():
        setattr(instance, key, value)


class FakeCompanyRepository:
    def __init__(self) -> None:
        self.companies: dict[uuid.UUID, Company] = {}

    async def create(self, **attrs: Any) -> Company:
        company = Company()
        _stamp(company, **attrs)
        self.companies[company.id] = company
        return company

    async def get_by_id(self, id: uuid.UUID) -> Company | None:
        return self.companies.get(id)

    async def get_by_cnpj(self, cnpj: str) -> Company | None:
        return next((c for c in self.companies.values() if c.cnpj == cnpj), None)


class FakeCampaignRepository:
    def __init__(self) -> None:
        self.campaigns: dict[uuid.UUID, Campaign] = {}

    async def create(self, **attrs: Any) -> Campaign:
        campaign = Campaign()
        _stamp(campaign, **attrs)
        self.campaigns[campaign.id] = campaign
        return campaign

    async def get_by_id(self, id: uuid.UUID) -> Campaign | None:
        return self.campaigns.get(id)


class FakeProspectRepository:
    def __init__(self) -> None:
        self.prospects: dict[uuid.UUID, Prospect] = {}

    async def create(self, **attrs: Any) -> Prospect:
        prospect = Prospect()
        _stamp(prospect, **attrs)
        self.prospects[prospect.id] = prospect
        return prospect

    async def update(self, instance: Prospect, **attrs: Any) -> Prospect:
        for key, value in attrs.items():
            setattr(instance, key, value)
        return instance

    async def get_by_id(self, id: uuid.UUID) -> Prospect | None:
        return self.prospects.get(id)

    async def list_by_mission(self, mission_id: uuid.UUID) -> Sequence[Prospect]:
        return [p for p in self.prospects.values() if p.mission_id == mission_id]


class FakeInteractionRepository:
    """Never exercised by this use case's flow (no register_interaction() call) —
    exists only because ProspectEngine's constructor requires one."""

    async def create(self, **attrs: Any) -> Interaction:
        interaction = Interaction()
        _stamp(interaction, **attrs)
        return interaction
