import re
from pathlib import Path

from app.ai.exceptions.prompt_exceptions import (
    MissingPromptVariableError,
    PromptNotFoundError,
    PromptVersionNotFoundError,
)
from app.ai.prompts.prompt_version import PromptVersion

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


class PromptRepository:
    """Loads, versions and renders AI prompts (e.g. "{{company}}", "{{segment}}",
    "{{city}}" placeholders).

    Backed by an in-memory registry (`register()`), optionally bootstrapped from a
    directory of flat `.md`/`.txt` files via `load_from_directory()` — each file becomes
    version 1 of a prompt named after the file stem. This is a lightweight stand-in for
    a future DB-backed store; the public methods won't need to change when that lands.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[PromptVersion]] = {}

    def register(
        self, name: str, content: str, *, version: int | None = None, activate: bool = True
    ) -> PromptVersion:
        existing = self._versions.setdefault(name, [])
        next_version = version if version is not None else max((v.version for v in existing), default=0) + 1
        prompt = PromptVersion(name=name, version=next_version, content=content)
        existing.append(prompt)
        if activate:
            self.activate_version(name, next_version)
        return prompt

    def load_from_directory(self, directory: Path, *, suffixes: tuple[str, ...] = (".md", ".txt")) -> None:
        if not directory.exists():
            return
        for file_path in sorted(directory.iterdir()):
            if file_path.is_file() and file_path.suffix in suffixes:
                self.register(file_path.stem, file_path.read_text(encoding="utf-8"))

    def list_versions(self, name: str) -> list[PromptVersion]:
        versions = self._versions.get(name)
        if not versions:
            raise PromptNotFoundError(name)
        return list(versions)

    def get_version(self, name: str, version: int) -> PromptVersion:
        for prompt in self.list_versions(name):
            if prompt.version == version:
                return prompt
        raise PromptVersionNotFoundError(name, version)

    def get_active(self, name: str) -> PromptVersion:
        for prompt in self.list_versions(name):
            if prompt.is_active:
                return prompt
        raise PromptNotFoundError(name)

    def activate_version(self, name: str, version: int) -> PromptVersion:
        versions = self.list_versions(name)
        target: PromptVersion | None = None
        for prompt in versions:
            if prompt.version == version:
                prompt.is_active = True
                target = prompt
            else:
                prompt.is_active = False
        if target is None:
            raise PromptVersionNotFoundError(name, version)
        return target

    def render(self, name: str, variables: dict[str, str], *, version: int | None = None) -> str:
        prompt = self.get_version(name, version) if version is not None else self.get_active(name)

        def _substitute(match: re.Match) -> str:
            key = match.group(1)
            if key not in variables:
                raise MissingPromptVariableError(name, key)
            return variables[key]

        return _PLACEHOLDER_PATTERN.sub(_substitute, prompt.content)

    @staticmethod
    def extract_placeholders(content: str) -> set[str]:
        return set(_PLACEHOLDER_PATTERN.findall(content))
