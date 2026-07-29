from typing import TYPE_CHECKING

from app.ai.exceptions.base import AIError

if TYPE_CHECKING:
    from app.ai.agents.enums import AgentType


class NoProviderAvailableError(AIError):
    def __init__(self) -> None:
        super().__init__("The orchestrator has no AI providers registered.")


class AgentNotRegisteredError(AIError):
    """`agent_type` is typed against AgentType for callers/type-checkers only — this
    module intentionally has no runtime dependency on `app.ai.agents` (exceptions are a
    leaf package; nothing should depend on agents just to raise an error about one)."""

    def __init__(self, agent_type: "AgentType") -> None:
        self.agent_type = agent_type
        super().__init__(f"No agent registered for AgentType.{agent_type.name}.")
