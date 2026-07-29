from typing import Any, ClassVar

from app.ai.providers.base.ai_provider import AIProvider


class ProviderBase(AIProvider):
    """Shared plumbing for every concrete provider: identity, config, default model.

    Deliberately does not implement any of AIProvider's abstract methods — every
    concrete provider still must (Python's ABC machinery enforces this at instantiation
    time), this class only removes the boilerplate around it.
    """

    provider_name: ClassVar[str] = "base"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        default_model: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.config = config or {}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} model={self.default_model!r}>"
