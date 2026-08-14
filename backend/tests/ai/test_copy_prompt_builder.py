import uuid
from datetime import datetime, timezone

from app.ai.agents.copy.copy_context_builder import CopyContext
from app.ai.agents.copy.copy_prompt_builder import CopyPromptBuilder
from app.models.mission.enums import MissionPriority, MissionStatus
from app.models.prospecting.enums import ProspectStage, ProspectStatus, ProspectTemperature
from app.outreach.models.enums import AssetType, Channel
from app.schemas.mission.mission import MissionRead
from app.schemas.prospecting.company import CompanyRead
from app.schemas.prospecting.prospect import ProspectRead


def _company() -> CompanyRead:
    return CompanyRead(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        legal_name="Agência XYZ Ltda",
        trade_name="Agência XYZ",
        cnpj="12345678000199",
        segment="Publicidade",
        city="Goiânia",
        state="GO",
    )


def _mission() -> MissionRead:
    return MissionRead(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        name="Expansão Goiânia",
        objective="Conseguir reunião",
        priority=MissionPriority.NORMAL,
        target_segment="Publicidade",
        target_city="Goiânia",
        status=MissionStatus.RUNNING,
    )


def _prospect() -> ProspectRead:
    return ProspectRead(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        company_id=uuid.uuid4(),
        campaign_id=uuid.uuid4(),
        mission_id=uuid.uuid4(),
        status=ProspectStatus.OPEN,
        temperature=ProspectTemperature.WARM,
        current_stage=ProspectStage.CONTACT_READY,
    )


def _worked_example_context(**overrides) -> CopyContext:
    defaults = dict(
        company=_company(),
        asset_type=AssetType.EMAIL,
        channel=Channel.EMAIL,
        tone="consultivo",
        language="pt-BR",
        recommendations=["Mencionar aumento de visibilidade em mídia indoor"],
        variables={"contact_name": "João", "objective": "Conseguir reunião"},
    )
    defaults.update(overrides)
    return CopyContext(**defaults)


def test_prompt_contains_every_section_header():
    builder = CopyPromptBuilder()
    prompt = builder.build(_worked_example_context())

    for header in (
        "## Context",
        "## Objective",
        "## Restrictions",
        "## Company",
        "## Prospect",
        "## Recommendations",
        "## Output Format",
    ):
        assert header in prompt


def test_prompt_carries_the_worked_example_data():
    builder = CopyPromptBuilder()
    prompt = builder.build(_worked_example_context())

    assert "Agência XYZ" in prompt
    assert "Goiânia" in prompt
    assert "Publicidade" in prompt
    assert "Conseguir reunião" in prompt
    assert "João" in prompt
    assert "email" in prompt
    assert "consultivo" in prompt


def test_output_format_section_demands_json_with_title_content_metadata():
    builder = CopyPromptBuilder()
    prompt = builder.build(_worked_example_context())

    assert '"title"' in prompt
    assert '"content"' in prompt
    assert '"metadata"' in prompt


def test_mission_section_appears_when_mission_is_present():
    builder = CopyPromptBuilder()
    prompt = builder.build(_worked_example_context(mission=_mission()))

    assert "## Mission" in prompt
    assert "Expansão Goiânia" in prompt


def test_prospect_section_includes_stage_and_temperature_when_prospect_is_present():
    builder = CopyPromptBuilder()
    prompt = builder.build(_worked_example_context(prospect=_prospect()))

    assert "Stage: contact_ready" in prompt
    assert "Temperature: warm" in prompt


def test_sections_with_no_data_are_omitted():
    builder = CopyPromptBuilder()
    context = CopyContext(
        company=None,
        asset_type=AssetType.WHATSAPP,
        variables={},
    )

    prompt = builder.build(context)

    assert "## Company" not in prompt
    assert "## Mission" not in prompt


def test_recommendations_section_includes_score_and_profile():
    builder = CopyPromptBuilder()
    context = _worked_example_context(
        commercial_score=82.5,
        commercial_profile={"segment_fit": "high"},
        recommendations=["Mencionar mídia indoor"],
    )

    prompt = builder.build(context)

    assert "82.5" in prompt
    assert "segment_fit" in prompt
    assert "Mencionar mídia indoor" in prompt
