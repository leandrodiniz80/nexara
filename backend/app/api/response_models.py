"""Shared response-shape reference for paginated `/cdn/metrics/*`
endpoints (Sprint 264). Documents the `{"items": [...], "meta": {...}}`
shape those endpoints converge on — not wired in as FastAPI
`response_model=` on any endpoint: every endpoint in `cdn.py` returns a
plain `dict` (not a typed Pydantic response), and the incident/audit-
event payloads these endpoints paginate are loosely-shaped dicts with no
existing Pydantic model of their own. Wiring `PaginatedResponse[T]` in as
an actual `response_model=` would mean either inventing item models for
incidents/audit-events now (a bigger, unrequested typing effort) or
risking Pydantic silently stripping fields FastAPI's response
serialization doesn't know about — a real regression risk for a
loosely-typed payload. This stays a reference shape (useful for OpenAPI
documentation of the pattern, or a future typed endpoint) that
`LoaderMetricsStore.paginate()`'s own return dict matches by convention.

IMPORTANT — this project already has a *different*, more established
pagination system: `app/api/responses/pagination.py`'s `Page`/
`PageMetadata`/`PageRequest` (fields: `page`, `page_size`, `total_items`,
`total_pages`), wired via `ApiResponse[T]` `response_model=` into most of
the *other* routers in this app (`auth.py`, `billing.py`, `branding.py`,
`health.py`, `logs.py`, `metrics.py` [the pre-existing `GET /api/v1/
metrics`, a different endpoint at a different prefix than anything in
`cdn.py`], `missions.py`, `organizations.py`, `outreach.py`,
`prospects.py`, `read_models.py`, `secure_demo.py`, `workspace.py`,
`audit.py`). `cdn.py` has never used that system across any of its 27+
prior sprints — it's a self-contained subsystem with its own plain-dict
`{"items", "total", "scope"}` envelope convention, and this sprint's own
requested shape (`per_page`/`has_next`, not `page_size`/`total_pages`)
doesn't match `Page`/`PageMetadata`'s field names either. Reusing that
existing system here would mean either renaming this sprint's requested
fields to match it, or importing a differently-shaped model and hoping
the field mismatch doesn't confuse `cdn.py`'s own consumers — a larger,
cross-subsystem unification this specific sprint didn't ask for. Flagged
here rather than silently duplicated without comment: worth deciding
deliberately in a future sprint whether `cdn.py` should ever adopt the
existing `Page`/`PageMetadata` convention instead of its own.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    total: int
    page: int
    per_page: int
    has_next: bool


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    meta: Meta
