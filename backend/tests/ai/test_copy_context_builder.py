import uuid
from datetime import datetime, timezone

import pytest

from app.ai.agents.copy.copy_context_builder import CopyContextBuilder
from app.ai.exceptions.agent_exceptions import AgentValidationError
from app.ai.schemas.ai_context import AIContext
from app.outreach.models.enums import AssetType, Channel
from app.schemas.prospecting.company import CompanyRead
from app.schemas.prospecting.contact import ContactRead


def _company(**overrides) -> CompanyRead:
    defaults = dict(
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
    defaults.update(overrides)
    return CompanyRead(**defaults)


def _contact(**overrides) -> ContactRead:
    defaults = dict(
        id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        company_id=uuid.uuid4(),
        full_name="João",
    )
    defaults.update(overrides)
    return ContactRead(**defaults)


def test_builds_context_with_asset_type_and_channel_from_variables():
    builder = CopyContextBuilder()
    context = AIContext(
        company=_company(),
        variables={"asset_type": "email", "channel": "email", "tone": "consultivo"},
    )

    copy_context = builder.build(context)

    assert copy_context.asset_type == AssetType.EMAIL
    assert copy_context.channel == Channel.EMAIL
    assert copy_context.tone == "consultivo"
    assert copy_context.company.trade_name == "Agência XYZ"


def test_missing_asset_type_raises():
    builder = CopyContextBuilder()
    context = AIContext(company=_company(), variables={})

    with pytest.raises(AgentValidationError):
        builder.build(context)


def test_unknown_asset_type_raises():
    builder = CopyContextBuilder()
    context = AIContext(company=_company(), variables={"asset_type": "carrier_pigeon"})

    with pytest.raises(AgentValidationError):
        builder.build(context)


def test_channel_is_none_when_not_provided():
    builder = CopyContextBuilder()
    context = AIContext(company=_company(), variables={"asset_type": "proposal"})

    copy_context = builder.build(context)

    assert copy_context.channel is None


def test_contact_name_falls_back_to_ai_context_contact():
    builder = CopyContextBuilder()
    context = AIContext(
        company=_company(), contact=_contact(), variables={"asset_type": "email"}
    )

    copy_context = builder.build(context)

    assert copy_context.variables["contact_name"] == "João"


def test_explicit_contact_name_variable_wins_over_ai_context_contact():
    builder = CopyContextBuilder()
    context = AIContext(
        company=_company(),
        contact=_contact(full_name="Outro Nome"),
        variables={"asset_type": "email", "contact_name": "João"},
    )

    copy_context = builder.build(context)

    assert copy_context.variables["contact_name"] == "João"


def test_control_keys_are_not_duplicated_into_variables():
    builder = CopyContextBuilder()
    context = AIContext(
        company=_company(),
        variables={
            "asset_type": "email",
            "channel": "email",
            "tone": "consultivo",
            "city": "Goiânia",
        },
    )

    copy_context = builder.build(context)

    assert "asset_type" not in copy_context.variables
    assert "channel" not in copy_context.variables
    assert "tone" not in copy_context.variables
    assert copy_context.variables["city"] == "Goiânia"


def test_commercial_data_is_read_from_memory():
    builder = CopyContextBuilder()
    context = AIContext(
        company=_company(),
        variables={"asset_type": "email"},
        memory=[
            {
                "commercial_profile": {"segment_fit": "high"},
                "commercial_score": 82.5,
                "recommendations": ["Mencionar visibilidade em mídia indoor"],
            }
        ],
    )

    copy_context = builder.build(context)

    assert copy_context.commercial_profile == {"segment_fit": "high"}
    assert copy_context.commercial_score == 82.5
    assert copy_context.recommendations == ["Mencionar visibilidade em mídia indoor"]


def test_commercial_data_defaults_when_memory_is_empty():
    builder = CopyContextBuilder()
    context = AIContext(company=_company(), variables={"asset_type": "email"})

    copy_context = builder.build(context)

    assert copy_context.commercial_profile is None
    assert copy_context.commercial_score is None
    assert copy_context.recommendations == []
