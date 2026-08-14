import enum
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from app.application.tasks.context.task_context import TaskContext


class TaskType(str, enum.Enum):
    RESEARCH = "research"
    COPY = "copy"
    QUALIFICATION = "qualification"
    PROPOSAL = "proposal"
    FOLLOWUP = "followup"


class ApplicationTask(ABC):
    """A unit of executable business work that bridges Workflow/Jobs/AI/Outreach/
    Sales Intelligence/Research without belonging to any one of them.

    Not a Job: no queue, priority, or progress tracking — that is JobEngine's job,
    and a Task may run *as* one via a JobExecutor if that's ever wired up. Not a
    Workflow: no step sequencing or branching. Not an Agent: no prompt/provider
    concerns — that's AgentBase's job. An ApplicationTask only calls into whichever
    of those already exists to get its work done; it never reaches a Provider, a
    database, or an external API directly.

    TaskExecutor (not this class) is what actually runs one — see
    executors/task_executor.py for why validate()/execute()/rollback() are kept as a
    plain interface here rather than a template method like AgentBase.execute().
    """

    task_type: ClassVar[TaskType]
    name: ClassVar[str]

    @abstractmethod
    def validate(self, context: TaskContext) -> None:
        """Raise TaskValidationError if `context` is missing what this task needs."""

    @abstractmethod
    async def execute(self, context: TaskContext) -> dict[str, Any]:
        """Do the task's work by calling into an existing module and return its
        outcome as a plain dict. TaskExecutor wraps this into a TaskResult; this
        method never constructs one itself."""

    @abstractmethod
    async def rollback(self, context: TaskContext) -> None:
        """Best-effort compensation, called by TaskExecutor when execute() raises.
        Several tasks in this sprint have nothing to undo (the module they call
        already manages its own partial state, or has no delete/undo operation to
        call) and implement this as a documented no-op."""
