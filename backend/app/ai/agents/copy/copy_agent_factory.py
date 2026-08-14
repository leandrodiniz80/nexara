from app.ai.agents.copy.copy_agent import CopyAgent
from app.ai.agents.copy.copy_context_builder import CopyContextBuilder
from app.ai.agents.copy.copy_prompt_builder import CopyPromptBuilder
from app.ai.agents.copy.copy_result_parser import CopyResultParser
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.providers.base.ai_provider import AIProvider
from app.ai.providers.mock_provider import MockProvider


def build_default_copy_agent(
    *,
    provider: AIProvider | None = None,
    prompt_repository: PromptRepository | None = None,
) -> CopyAgent:
    """Composition root for a standalone CopyAgent (outside of a full AIOrchestrator).
    Defaults to MockProvider, same reasoning as build_default_orchestrator(): safe to
    run with no API keys configured. Swapping in a real AIProvider is the only change
    needed here — CopyAgent/CopyPromptBuilder/CopyContextBuilder/CopyResultParser
    never change.
    """
    return CopyAgent(
        provider or MockProvider(),
        prompt_repository or PromptRepository(),
        context_builder=CopyContextBuilder(),
        prompt_builder=CopyPromptBuilder(),
        result_parser=CopyResultParser(),
    )
