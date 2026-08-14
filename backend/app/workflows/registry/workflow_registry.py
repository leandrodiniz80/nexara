import uuid

from app.workflows.exceptions.workflow_exceptions import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)
from app.workflows.models.workflow import Workflow


class WorkflowRegistry:
    """Catalog of Workflow *definitions*, versioned like PromptRepository
    (app/ai/prompts) — register a new version, look up the currently active one by
    name, or a specific version explicitly. Registering multiple versions under the
    same name never overwrites an older one; `activate_version()` is the only thing
    that changes which version `get_active()` returns.
    """

    def __init__(self) -> None:
        self._versions: dict[str, list[Workflow]] = {}
        self._active_version: dict[str, int] = {}
        self._by_id: dict[uuid.UUID, Workflow] = {}

    def register(self, workflow: Workflow, *, activate: bool = True) -> Workflow:
        self._versions.setdefault(workflow.name, []).append(workflow)
        self._by_id[workflow.id] = workflow
        if activate:
            self._active_version[workflow.name] = workflow.version
        return workflow

    def get_by_id(self, workflow_id: uuid.UUID) -> Workflow | None:
        return self._by_id.get(workflow_id)

    def get_active(self, name: str) -> Workflow:
        versions = self._versions.get(name)
        if not versions:
            raise WorkflowNotFoundError(name)
        active_version = self._active_version.get(name)
        for workflow in versions:
            if workflow.version == active_version:
                return workflow
        raise WorkflowNotFoundError(name)

    def get_version(self, name: str, version: int) -> Workflow:
        for workflow in self._versions.get(name, []):
            if workflow.version == version:
                return workflow
        raise WorkflowVersionNotFoundError(name, version)

    def activate_version(self, name: str, version: int) -> Workflow:
        workflow = self.get_version(name, version)
        self._active_version[name] = version
        return workflow

    def list_workflows(self) -> list[str]:
        return list(self._versions.keys())

    def list_versions(self, name: str) -> list[Workflow]:
        return list(self._versions.get(name, []))
