from app.presentation.executive_payload import ExecutivePayload
from app.presentation.executive_view import ExecutiveView

_APPLICATION_NAME = "Elevel Prospect AI"
_APPLICATION_VERSION = "1.0.0"


class ExecutivePayloadService:
    """Transforms an already-composed ExecutiveView into ExecutivePayload —
    the platform's public, serializable DTO. Never recalculates data, never
    modifies a list, never modifies a value, never alters a string; only
    copies. `generated_at` is preserved exactly as it came from the
    ExecutiveView, never re-stamped. No domain-module import, no Engine, no
    Adapter, no persistence, no integration, no API, no JSON — just DTO
    transformation.

    ExecutiveViewService remains the only place responsible for composing
    the platform's Views into one ExecutiveView; this class only ever
    turns that already-composed object into its public, transport-ready
    shape.
    """

    def build(self, view: ExecutiveView) -> ExecutivePayload:
        return ExecutivePayload(
            title=view.report.title,
            generated_at=view.generated_at,
            dashboard=view.dashboard,
            report=view.report,
            kpis=list(view.kpis),
            metadata={
                "application": _APPLICATION_NAME,
                "version": _APPLICATION_VERSION,
                "generated_at": view.generated_at,
            },
        )
