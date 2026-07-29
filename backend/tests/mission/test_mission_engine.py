import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.mission.enums import MissionStatus
from app.models.prospecting.enums import ProspectStage, ProspectStatus
from app.schemas.mission.enums import PipelineHealth
from app.services.mission.exceptions import InvalidMissionTransitionError
from app.services.mission.mission_engine import MissionEngine
from app.services.mission.mission_timeline import MissionTimeline
from tests.mission.fakes import (
    FakeMissionEventRepository,
    FakeMissionMetricsRepository,
    FakeMissionRepository,
    FakeProspectRepository,
)


def _build_engine():
    mission_repo = FakeMissionRepository()
    metrics_repo = FakeMissionMetricsRepository()
    prospect_repo = FakeProspectRepository()
    event_repo = FakeMissionEventRepository()
    timeline = MissionTimeline(event_repo)
    engine = MissionEngine(mission_repo, metrics_repo, prospect_repo, timeline)
    return engine, mission_repo, metrics_repo, prospect_repo, event_repo


async def test_create_sets_up_mission_metrics_and_timeline_event():
    engine, _, metrics_repo, _, event_repo = _build_engine()

    mission = await engine.create(name="Missão Verão 2027", target_quantity=50)

    assert mission.status == MissionStatus.DRAFT
    assert mission.progress == 0

    metrics = await metrics_repo.get_by_mission(mission.id)
    assert metrics is not None
    assert metrics.prospects_created == 0

    events = await event_repo.list_by_mission(mission.id)
    assert len(events) == 1
    assert events[0].event == "mission_created"


async def test_lifecycle_happy_path():
    engine, *_ = _build_engine()
    mission = await engine.create(name="Missão X")

    mission = await engine.start(mission)
    assert mission.status == MissionStatus.RUNNING
    assert mission.started_at is not None

    mission = await engine.pause(mission)
    assert mission.status == MissionStatus.PAUSED

    mission = await engine.resume(mission)
    assert mission.status == MissionStatus.RUNNING

    mission = await engine.finish(mission)
    assert mission.status == MissionStatus.FINISHED
    assert mission.progress == 100
    assert mission.finished_at is not None


async def test_cannot_pause_a_mission_that_is_not_running():
    engine, *_ = _build_engine()
    mission = await engine.create(name="Missão Y")

    with pytest.raises(InvalidMissionTransitionError):
        await engine.pause(mission)


async def test_cancel_is_allowed_from_draft():
    engine, *_ = _build_engine()
    mission = await engine.create(name="Missão Z")

    mission = await engine.cancel(mission, reason="Cliente desistiu")

    assert mission.status == MissionStatus.CANCELLED
    assert mission.finished_at is not None


async def test_cannot_cancel_a_finished_mission():
    engine, *_ = _build_engine()
    mission = await engine.create(name="Missão W")
    mission = await engine.start(mission)
    mission = await engine.finish(mission)

    with pytest.raises(InvalidMissionTransitionError):
        await engine.cancel(mission)


async def test_calculate_metrics_derives_counts_from_prospects():
    engine, _, _, prospect_repo, _ = _build_engine()
    mission = await engine.create(name="Missão Metrics", target_quantity=10)

    company_a = uuid.uuid4()
    company_b = uuid.uuid4()
    now = datetime.now(timezone.utc)

    prospect_repo.seed(
        mission_id=mission.id,
        company_id=company_a,
        status=ProspectStatus.WON,
        current_stage=ProspectStage.WON,
        qualified_at=now,
        estimated_value=Decimal("10000"),
    )
    prospect_repo.seed(
        mission_id=mission.id,
        company_id=company_b,
        status=ProspectStatus.LOST,
        current_stage=ProspectStage.LOST,
        qualified_at=now,
        estimated_value=Decimal("5000"),
    )
    prospect_repo.seed(
        mission_id=mission.id,
        company_id=company_a,
        status=ProspectStatus.OPEN,
        current_stage=ProspectStage.MEETING,
        qualified_at=now,
    )

    metrics = await engine.calculate_metrics(mission)

    assert metrics.companies_found == 2
    assert metrics.companies_qualified == 2
    assert metrics.prospects_created == 3
    assert metrics.meetings == 2
    assert metrics.contracts == 1
    assert metrics.won_value == Decimal("10000")
    assert metrics.lost_value == Decimal("5000")
    assert metrics.conversion_rate == 33.33
    assert metrics.meeting_rate == 66.67


async def test_calculate_progress_averages_the_targets_that_are_set():
    engine, _, _, prospect_repo, _ = _build_engine()
    mission = await engine.create(name="Missão Progress", target_quantity=4, target_meetings=2)

    prospect_repo.seed(mission_id=mission.id, status=ProspectStatus.OPEN, current_stage=ProspectStage.MEETING)
    prospect_repo.seed(mission_id=mission.id, status=ProspectStatus.OPEN, current_stage=ProspectStage.NEW)

    progress = await engine.calculate_progress(mission)

    # quantity: 2/4 = 50% ; meetings: 1/2 = 50% -> average 50%
    assert progress == 50
    assert mission.progress == 50


async def test_forecast_completion_is_none_before_the_mission_starts():
    engine, *_ = _build_engine()
    mission = await engine.create(name="Missão Forecast", target_quantity=10)

    assert await engine.forecast_completion(mission) is None


async def test_forecast_completion_projects_a_date_from_current_pace():
    engine, _, _, prospect_repo, _ = _build_engine()
    mission = await engine.create(name="Missão Forecast 2", target_quantity=10)
    mission = await engine.start(mission)
    mission.started_at = datetime.now(timezone.utc) - timedelta(days=5)

    for _ in range(5):
        prospect_repo.seed(mission_id=mission.id, status=ProspectStatus.OPEN, current_stage=ProspectStage.NEW)
    await engine.calculate_metrics(mission)  # refresh the snapshot forecast_completion() reads

    forecast = await engine.forecast_completion(mission)

    assert forecast is not None
    assert mission.estimated_completion == forecast


async def test_summary_recommends_starting_research_when_there_are_no_prospects():
    engine, *_ = _build_engine()
    mission = await engine.create(name="Missão Summary")

    summary = await engine.summary(mission)

    assert summary.total_prospects == 0
    assert summary.contracts == 0
    assert summary.next_recommended_action.startswith("Nenhum prospect")
    assert summary.pipeline_health in {PipelineHealth.HEALTHY, PipelineHealth.AT_RISK, PipelineHealth.CRITICAL}


async def test_summary_estimated_revenue_includes_weighted_open_pipeline():
    engine, _, _, prospect_repo, _ = _build_engine()
    mission = await engine.create(name="Missão Revenue")

    prospect_repo.seed(
        mission_id=mission.id,
        status=ProspectStatus.OPEN,
        current_stage=ProspectStage.NEGOTIATION,
        estimated_value=Decimal("10000"),
        probability=50,
    )
    prospect_repo.seed(
        mission_id=mission.id,
        status=ProspectStatus.WON,
        current_stage=ProspectStage.WON,
        estimated_value=Decimal("2000"),
    )

    summary = await engine.summary(mission)

    # won (2000) + weighted open (10000 * 50%) = 7000
    assert summary.estimated_revenue == Decimal("7000")


async def test_mission_timeline_records_and_lists_events_in_order():
    event_repo = FakeMissionEventRepository()
    timeline = MissionTimeline(event_repo)
    mission_id = uuid.uuid4()

    await timeline.record(mission_id, "campaign_created", description="Campanha X criada.")
    await timeline.record(mission_id, "research_started")

    events = await timeline.list_timeline(mission_id)

    assert [e.event for e in events] == ["campaign_created", "research_started"]
