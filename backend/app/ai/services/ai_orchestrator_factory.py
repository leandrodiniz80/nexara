from app.ai.agents.analytics_agent import AnalyticsAgent
from app.ai.agents.copy_agent import CopyAgent
from app.ai.agents.enrichment_agent import EnrichmentAgent
from app.ai.agents.enums import AgentType
from app.ai.agents.qualification_agent import QualificationAgent
from app.ai.agents.research_agent import ResearchAgent
from app.ai.agents.review_agent import ReviewAgent
from app.ai.agents.sales_strategy_agent import SalesStrategyAgent
from app.ai.orchestrator.ai_orchestrator import AIOrchestrator
from app.ai.prompts.prompt_repository import PromptRepository
from app.ai.providers.base.ai_provider import AIProvider
from app.ai.providers.mock_provider import MockProvider


def build_default_orchestrator(
    *, providers: dict[str, AIProvider] | None = None, prompt_repository: PromptRepository | None = None
) -> AIOrchestrator:
    """Composition root for the AI module: the one place that decides which concrete
    providers/agents/prompts back an AIOrchestrator.

    Defaults to a single MockProvider bound to every agent — safe to run with no API
    keys configured. Swap `providers`/individual agents' constructor call here once a
    real provider (OpenAIProvider, ClaudeProvider, ...) is ready; nothing outside this
    factory needs to change.
    """
    providers = providers if providers is not None else {"mock": MockProvider()}
    default_provider = next(iter(providers.values()))
    prompt_repository = prompt_repository if prompt_repository is not None else PromptRepository()

    agents = {
        AgentType.RESEARCH: ResearchAgent(default_provider, prompt_repository),
        AgentType.QUALIFICATION: QualificationAgent(default_provider, prompt_repository),
        AgentType.ENRICHMENT: EnrichmentAgent(default_provider, prompt_repository),
        AgentType.SALES_STRATEGY: SalesStrategyAgent(default_provider, prompt_repository),
        AgentType.COPY: CopyAgent(default_provider, prompt_repository),
        AgentType.REVIEW: ReviewAgent(default_provider, prompt_repository),
        AgentType.ANALYTICS: AnalyticsAgent(default_provider, prompt_repository),
    }

    return AIOrchestrator(providers=providers, agents=agents, prompt_repository=prompt_repository)
