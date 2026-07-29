from app.ai.exceptions.base import AIError


class PromptError(AIError):
    """Base class for prompt-repository failures."""


class PromptNotFoundError(PromptError):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"No prompt registered under name '{name}'.")


class PromptVersionNotFoundError(PromptError):
    def __init__(self, name: str, version: int) -> None:
        self.name = name
        self.version = version
        super().__init__(f"Prompt '{name}' has no version {version}.")


class MissingPromptVariableError(PromptError):
    def __init__(self, name: str, variable: str) -> None:
        self.name = name
        self.variable = variable
        super().__init__(f"Prompt '{name}' requires placeholder '{{{{{variable}}}}}' which was not provided.")
