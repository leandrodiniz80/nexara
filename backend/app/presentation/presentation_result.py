from pydantic import BaseModel, ConfigDict

from app.presentation.executive_payload import ExecutivePayload
from app.presentation.executive_view import ExecutiveView
from app.presentation.response_envelope import ResponseEnvelope


class PresentationResult(BaseModel):
    """The frozen outcome of running the Presentation layer's full
    composition chain end to end — the ExecutiveView, the ExecutivePayload
    built from it, and the ResponseEnvelope wrapping that payload. Nothing
    here is calculated by this type itself; it only holds what
    PresentationCoordinator already obtained by delegating to
    ExecutiveViewService, ExecutivePayloadService and
    ResponseEnvelopeService.
    """

    model_config = ConfigDict(frozen=True)

    view: ExecutiveView
    payload: ExecutivePayload
    response: ResponseEnvelope
