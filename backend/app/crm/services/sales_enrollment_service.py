from datetime import datetime
from typing import Any

from app.crm.models.crm_opportunity import CRMOpportunity
from app.crm.services.sales_cadence import SalesCadence
from app.crm.services.sales_cadence_execution_service import SalesCadenceExecutionService
from app.crm.services.sales_enrollment import SalesEnrollment
from app.crm.services.sales_playbook import SalesPlaybook


class SalesEnrollmentService:
    """Aggregates a CRMOpportunity, a SalesPlaybook and a SalesCadence into a
    single SalesEnrollment, starting the cadence's execution in the same
    step. It creates nothing but this in-memory link and starts nothing but
    the one SalesCadenceExecution its own contract requires — no CRMEngine,
    no Runtime, no Workflow, no Automation, no Scheduler, no AI, no Adapter,
    no Rule, no Decision. Its only collaborator is the already-existing
    SalesCadenceExecutionService.
    """

    def __init__(self, execution_service: SalesCadenceExecutionService) -> None:
        self._execution_service = execution_service

    def enroll(
        self,
        opportunity: CRMOpportunity,
        playbook: SalesPlaybook,
        cadence: SalesCadence,
        *,
        now: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SalesEnrollment:
        execution = self._execution_service.start(cadence, opportunity, now=now)
        return SalesEnrollment(
            opportunity=opportunity,
            playbook=playbook,
            cadence=cadence,
            execution=execution,
            started_at=execution.started_at,
            status=execution.status,
            metadata=dict(metadata or {}),
        )
