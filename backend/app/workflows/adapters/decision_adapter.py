from app.decision.builders.decision_builder import DecisionBuilder
from app.decision.engine.decision_engine import DecisionEngine
from app.decision.models.enums import DecisionType
from app.workflows.schemas.workflow_request import WorkflowRequest


class WorkflowDecisionUnavailableError(Exception):
    """Raised when the Decision Engine can't select a Workflow for a given
    request. WorkflowEngine._resolve_workflow() catches this (along with
    anything else RealDecisionAdapter might raise) and falls back to the
    originally requested workflow_name — exactly as if no adapter existed.
    """

    def __init__(self, requested_workflow_name: str) -> None:
        self.requested_workflow_name = requested_workflow_name
        super().__init__(
            f"Decision Engine could not choose a workflow for request "
            f"'{requested_workflow_name}'."
        )


class RealDecisionAdapter:
    """The concrete bridge between app.workflows and app.decision — the only
    file in app.workflows allowed to import app.decision, encapsulating it
    completely. WorkflowEngine never imports this class: it only depends on the
    structural `choose_workflow(request) -> str` shape (its own local
    DecisionAdapter Protocol in app.workflows.engine.workflow_engine), so this
    class is wired in exclusively through a composition root
    (workflow_engine_factory.py) or directly by a caller — never by
    workflow_engine.py itself.
    """

    def __init__(self, decision_engine: DecisionEngine) -> None:
        self.decision_engine = decision_engine

    def choose_workflow(self, request: WorkflowRequest) -> str:
        context = DecisionBuilder.context(variables=dict(request.context.variables))
        result = self.decision_engine.decide(DecisionType.WORKFLOW, context)
        if not result.success or result.selected_option is None:
            raise WorkflowDecisionUnavailableError(request.workflow_name)
        return result.selected_option.name
