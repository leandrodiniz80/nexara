from app.ai.exceptions.base import AIError


class AgentError(AIError):
    """Base class for agent failures."""


class AgentValidationError(AgentError):
    """Raised by Agent.validate() when the given AIContext is insufficient for the agent to run."""


class AgentExecutionError(AgentError):
    """Raised when an agent's core logic fails in a way that isn't a validation problem."""
