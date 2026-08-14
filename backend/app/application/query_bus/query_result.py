from typing import Any

from pydantic import BaseModel, ConfigDict


class QueryResult(BaseModel):
    """The frozen outcome of dispatching one QueryRequest through
    QueryBus. `reason` is populated whenever `success` is False — either
    the query is unknown, or (this sprint, always) no QueryHandler is
    registered for it yet.
    """

    model_config = ConfigDict(frozen=True)

    success: bool
    query_name: str
    payload: Any | None = None
    reason: str | None = None
    execution_time: float
