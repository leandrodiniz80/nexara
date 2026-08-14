from app.crm.exceptions.base import CRMError
from app.crm.exceptions.crm_exceptions import (
    CompanyNotFoundError,
    ContactNotFoundError,
    OpportunityNotFoundError,
    PipelineNotFoundError,
    StageNotFoundError,
)

__all__ = [
    "CRMError",
    "CompanyNotFoundError",
    "ContactNotFoundError",
    "OpportunityNotFoundError",
    "PipelineNotFoundError",
    "StageNotFoundError",
]
