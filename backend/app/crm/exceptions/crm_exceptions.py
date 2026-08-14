import uuid

from app.crm.exceptions.base import CRMError


class CompanyNotFoundError(CRMError):
    def __init__(self, company_id: uuid.UUID) -> None:
        self.company_id = company_id
        super().__init__(f"No CRMCompany found with id {company_id}.")


class ContactNotFoundError(CRMError):
    def __init__(self, contact_id: uuid.UUID) -> None:
        self.contact_id = contact_id
        super().__init__(f"No CRMContact found with id {contact_id}.")


class OpportunityNotFoundError(CRMError):
    def __init__(self, opportunity_id: uuid.UUID) -> None:
        self.opportunity_id = opportunity_id
        super().__init__(f"No CRMOpportunity found with id {opportunity_id}.")


class PipelineNotFoundError(CRMError):
    def __init__(self, pipeline_id: uuid.UUID) -> None:
        self.pipeline_id = pipeline_id
        super().__init__(f"No CRMPipeline found with id {pipeline_id}.")


class StageNotFoundError(CRMError):
    def __init__(self, stage_id: uuid.UUID) -> None:
        self.stage_id = stage_id
        super().__init__(f"No CRMStage found with id {stage_id} in the opportunity's pipeline.")
