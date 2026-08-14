from typing import Any

from pydantic import BaseModel, ConfigDict


class QueryRequest(BaseModel):
    """One request to dispatch a public query through QueryBus — frozen.
    `payload` stays genuinely `Any`: QueryBus never inspects or transforms
    it.
    """

    model_config = ConfigDict(frozen=True)

    query_name: str
    payload: Any | None = None
    request_id: str | None = None
