import uuid
from datetime import datetime, timezone
from typing import Sequence

from app.models.mission.mission import Mission
from app.models.mission.mission_event import MissionEvent
from app.models.mission.mission_metrics import MissionMetrics
from app.models.prospecting.prospect import Prospect


def _stamp(instance, **attrs) -> None:
    """Fills in what a real flush-to-DB would normally do: id + audit timestamps."""
    instance.id = uuid.uuid4()
    instance.created_at = attrs.pop("created_at", datetime.now(timezone.utc))
    instance.updated_at = instance.created_at
    for key, value in attrs.items():
        setattr(instance, key, value)


class FakeMissionRepository:
    def __init__(self) -> None:
        self.store: dict[uuid.UUID, Mission] = {}

    async def create(self, **attrs) -> Mission:
        mission = Mission()
        _stamp(mission, **attrs)
        self.store[mission.id] = mission
        return mission

    async def update(self, instance: Mission, **attrs) -> Mission:
        for key, value in attrs.items():
            setattr(instance, key, value)
        return instance

    async def get_by_id(self, id: uuid.UUID) -> Mission | None:
        return self.store.get(id)


class FakeMissionMetricsRepository:
    def __init__(self) -> None:
        self.store: dict[uuid.UUID, MissionMetrics] = {}

    async def create(self, **attrs) -> MissionMetrics:
        metrics = MissionMetrics()
        defaults = dict(
            companies_found=0,
            companies_qualified=0,
            prospects_created=0,
            emails_generated=0,
            emails_approved=0,
            emails_sent=0,
            emails_opened=0,
            emails_replied=0,
            meetings=0,
            proposals=0,
            contracts=0,
            won_value=0,
            lost_value=0,
            conversion_rate=None,
            response_rate=None,
            meeting_rate=None,
        )
        defaults.update(attrs)
        _stamp(metrics, **defaults)
        self.store[metrics.mission_id] = metrics
        return metrics

    async def update(self, instance: MissionMetrics, **attrs) -> MissionMetrics:
        for key, value in attrs.items():
            setattr(instance, key, value)
        return instance

    async def get_by_mission(self, mission_id: uuid.UUID) -> MissionMetrics | None:
        return self.store.get(mission_id)


class FakeMissionEventRepository:
    def __init__(self) -> None:
        self.events: list[MissionEvent] = []

    async def create(self, **attrs) -> MissionEvent:
        event = MissionEvent()
        _stamp(event, **attrs)
        self.events.append(event)
        return event

    async def list_by_mission(self, mission_id: uuid.UUID) -> Sequence[MissionEvent]:
        return [e for e in self.events if e.mission_id == mission_id]


class FakeProspectRepository:
    def __init__(self) -> None:
        self.prospects: list[Prospect] = []

    def seed(self, **attrs) -> Prospect:
        prospect = Prospect()
        defaults = dict(
            company_id=uuid.uuid4(),
            campaign_id=uuid.uuid4(),
            qualified_at=None,
            estimated_value=None,
            probability=None,
        )
        defaults.update(attrs)
        _stamp(prospect, **defaults)
        self.prospects.append(prospect)
        return prospect

    async def list_by_mission(self, mission_id: uuid.UUID) -> Sequence[Prospect]:
        return [p for p in self.prospects if p.mission_id == mission_id]
