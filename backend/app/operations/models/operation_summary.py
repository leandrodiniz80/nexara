from pydantic import BaseModel, ConfigDict


class OperationSummary(BaseModel):
    """A frozen count of all tracked Operations by state, at one point in
    time. OperationsEngine.summary() always returns a fresh one.
    """

    model_config = ConfigDict(frozen=True)

    total_operations: int
    running_operations: int
    finished_operations: int
    failed_operations: int
