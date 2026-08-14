import uuid
from datetime import datetime, timezone

from app.ai.agents.copy.copy_agent import CopyAgent
from app.ai.agents.copy.copy_agent_factory import build_default_copy_agent
from app.ai.agents.copy.copy_result_parser import CopyResultParser
from app.ai.agents.enums import AgentType
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.providers.mock_provider import MockProvider
from app.ai.schemas.ai_context import AIContext
from app.outreach.render.rendered_asset import RenderedAsset
from app.schemas.prospecting.company import CompanyRead


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


def _worked_example_context() -> AIContext:
    return AIContext(
        company=_company(),
        variables={
            "asset_type": "email",
            "channel": "email",
            "tone": "consultivo",
            "contact_name": "João",
            "objective": "Conseguir reunião",
        },
    )


async def test_copy_agent_generates_an_asset_via_agent_base_execute():
    agent = build_default_copy_agent()

    result = await agent.execute(_worked_example_context())

    assert result.success is True
    assert result.agent_name == "copy_agent"
    assert result.provider == "mock"
    rendered = RenderedAsset(**result.payload)
    assert rendered.content
    assert rendered.metadata["asset_type"] == "email"
    assert rendered.metadata["tone"] == "consultivo"


async def test_copy_agent_fails_gracefully_without_company():
    agent = build_default_copy_agent()
    context = AIContext(variables={"asset_type": "email"})

    result = await agent.execute(context)

    assert result.success is False
    assert any("failed" in log for log in result.logs)


async def test_copy_agent_fails_gracefully_with_unknown_asset_type():
    agent = build_default_copy_agent()
    context = AIContext(company=_company(), variables={"asset_type": "carrier_pigeon"})

    result = await agent.execute(context)

    assert result.success is False


async def test_copy_agent_prompt_reaches_the_provider_with_worked_example_data():
    """Uses the real MockProvider (never a hand-rolled fake) — it just echoes back the
    first 120 chars of whatever prompt it receives, which is enough to prove
    CopyPromptBuilder's output (Context + Objective sections, in this case) is what
    actually gets sent, not some hardcoded string."""
    agent = build_default_copy_agent()

    result = await agent.execute(_worked_example_context())

    assert result.success is True
    assert "mock:generate" in result.payload["content"]
    assert "Conseguir reunião" in result.payload["content"]
    assert "consultivo" in result.payload["content"]


def test_copy_agent_never_imports_a_concrete_provider():
    import app.ai.agents.copy.copy_agent as copy_agent_module

    with open(copy_agent_module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()
    for forbidden in ("OpenAI", "Claude", "Gemini", "DeepSeek", "Mistral"):
        assert forbidden not in source


async def test_copy_agent_end_to_end_through_ai_orchestrator():
    from app.ai.services.ai_orchestrator_factory import build_default_orchestrator

    orchestrator = build_default_orchestrator()

    result = await orchestrator.execute(AgentType.COPY, _worked_example_context())

    assert result.success is True
    assert result.agent_name == "copy_agent"
    logs = orchestrator.list_execution_logs()
    assert logs[-1].agent_name == "copy_agent"


def test_result_parser_can_reconstruct_rendered_asset_from_agent_payload():
    """CopyResultParser's literal "AgentResult.payload -> RenderedAsset" job."""
    parser = CopyResultParser()
    payload = {"title": None, "content": "Oi João", "metadata": {"tone": "consultivo"}}

    rendered = parser.from_agent_payload(payload)

    assert rendered.content == "Oi João"


async def test_custom_provider_can_be_injected_without_touching_copy_agent():
    custom_provider = MockProvider(default_model="mock-2")
    agent = CopyAgent(custom_provider, PromptRepository())

    result = await agent.execute(_worked_example_context())

    assert result.model == "mock-2"
