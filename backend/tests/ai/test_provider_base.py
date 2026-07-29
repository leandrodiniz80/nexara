import pytest

from app.ai.providers.base.provider_base import ProviderBase
from app.ai.providers.mock_provider import MockProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.schemas.ai_context import AIMessage


def test_provider_base_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ProviderBase()


async def test_mock_provider_generate_returns_response():
    provider = MockProvider()
    response = await provider.generate("Diga ola para a Coca-Cola")
    assert response.content.startswith("[mock:generate]")
    assert response.input_tokens is not None
    assert response.output_tokens is not None


async def test_mock_provider_chat_uses_last_user_message():
    provider = MockProvider()
    messages = [
        AIMessage(role="system", content="Você é um assistente de vendas."),
        AIMessage(role="user", content="Quem é o decisor da Coca-Cola?"),
    ]
    response = await provider.chat(messages)
    assert "Quem é o decisor da Coca-Cola?" in response.content


async def test_mock_provider_embed_is_deterministic():
    provider = MockProvider()
    first = await provider.embed("Coca-Cola")
    second = await provider.embed("Coca-Cola")
    assert first.vectors == second.vectors
    assert len(first.vectors[0]) == 8


async def test_mock_provider_classify_picks_one_of_the_labels():
    provider = MockProvider()
    result = await provider.classify("empresa de bebidas", labels=["quente", "morno", "frio"])
    assert result.label in {"quente", "morno", "frio"}


def test_mock_provider_estimate_cost_is_zero():
    provider = MockProvider()
    assert provider.estimate_cost(1000, 500) == 0


async def test_mock_provider_health_check_is_true():
    provider = MockProvider()
    assert await provider.health_check() is True


async def test_stub_provider_methods_raise_not_implemented():
    provider = OpenAIProvider()
    with pytest.raises(NotImplementedError):
        await provider.generate("oi")
    with pytest.raises(NotImplementedError):
        provider.estimate_tokens("oi")
    with pytest.raises(NotImplementedError):
        await provider.health_check()
