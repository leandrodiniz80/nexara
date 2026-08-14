from pydantic import BaseModel, Field

from app.crm.models.crm_opportunity import CRMOpportunity
from app.runtime.models.execution_result import ExecutionResult


class ExecutionProcessingResult(BaseModel):
    """What ExecutionResultProcessor.process() returns — the technical
    ExecutionResult Runtime produced, plus whatever commercial effect (today:
    a CRM opportunity) was derived from it. Mutable, like RuleResult/
    DecisionResult: a caller (ProspectingRuntimeApplicationService) may still
    need to merge in warnings gathered before process() was ever called
    (e.g. from an optional Decision/Business Rules pre-check this processor
    never sees).
    """

    execution_result: ExecutionResult
    crm_opportunity: CRMOpportunity | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time: float
