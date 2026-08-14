import uuid
from typing import Any

from pydantic import BaseModel, Field


class TraceContext(BaseModel):
    """Everything one traced execution needs to correlate itself with whatever
    triggered it — the same "opaque cross-module reference, never the full entity"
    convention TaskContext/AIContext already use. A future caller builds one of
    these from whatever ids it already has (a Mission, a Job, an HTTP request) and
    hands it to ObservabilityEngine.start_trace().
    """

    correlation_id: uuid.UUID | None = None
    request_id: str | None = None
    mission_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
