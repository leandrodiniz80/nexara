from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OperationContext(BaseModel):
    """One request to run an Operation through OperationsCoordinator —
    frozen.
    """

    model_config = ConfigDict(frozen=True)

    operation_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
