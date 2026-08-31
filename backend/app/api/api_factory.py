from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.docs.openapi import API_DESCRIPTION, API_TITLE, API_VERSION, OPENAPI_TAGS
from app.api.exceptions.handlers import register_exception_handlers
from app.api.middleware.logging import LoggingMiddleware
from app.api.middleware.request_id import RequestIdMiddleware
from app.api.middleware.tenant import TenantMiddleware
from app.api.middleware.timing import TimingMiddleware
from app.api.middleware.tracing import TracingMiddleware
from app.api.routers.audit import router as audit_router
from app.api.routers.auth import router as auth_router
from app.api.routers.billing import router as billing_router
from app.api.routers.branding import router as branding_router
from app.api.routers.cdn import router as cdn_router
from app.api.routers.health import router as health_router
from app.api.routers.logs import router as logs_router
from app.api.routers.metrics import router as metrics_router
from app.api.routers.missions import router as missions_router
from app.api.routers.organizations import router as organizations_router
from app.api.routers.outreach import router as outreach_router
from app.api.routers.prospects import router as prospects_router
from app.api.routers.read_models import router as read_models_router
from app.api.routers.secure_demo import router as secure_demo_router
from app.api.routers.tenants import router as tenants_router
from app.api.routers.workspace import router as workspace_router
from app.core.config import settings


def create_app() -> FastAPI:
    """Composition root for the whole HTTP layer — one FastAPI instance, wired with
    every middleware, router and exception handler this sprint builds.
    `app/main.py` calls this exactly once; nothing else should construct a FastAPI
    app for this platform.
    """
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "displayRequestDuration": True,
            "docExpansion": "list",
        },
    )

    # Registered innermost-first: the *last* middleware added runs *first* on the
    # way in (and last on the way out) — RequestIdMiddleware must be outermost of
    # the original three so request.state.request_id exists before Timing/Logging
    # (or any exception handler) ever look for it. TracingMiddleware is added
    # after that so request.state.correlation_id is set before anything else
    # runs, and its trace log captures the complete round trip. CORSMiddleware is
    # added last of all (truly outermost) so it can answer a browser's OPTIONS
    # preflight — and attach Access-Control-* headers to every response, including
    # error ones — before any other middleware or route ever runs.
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(TimingMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(TracingMiddleware)
    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        # Railway mints a new random subdomain for the frontend service on
        # every deploy (b1eb, 07d1, ...), so a fixed allow_origins list keeps
        # going stale one deploy after the next. This regex covers any
        # "invigorating-stillness-production-*" domain Railway generates,
        # without needing an env var update each time.
        allow_origin_regex=r"https://invigorating-stillness-production-[a-z0-9]+\.up\.railway\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    # Every other router already sits under settings.API_V1_PREFIX; health.py
    # itself stays prefix-less so the pre-existing bare "/" and "/health"
    # (used by Railway's own healthcheck) keep working unchanged — this
    # second registration adds "/api/v1/health" alongside them without
    # touching health.py at all.
    app.include_router(health_router, prefix=settings.API_V1_PREFIX)
    app.include_router(missions_router)
    app.include_router(prospects_router)
    app.include_router(workspace_router)
    app.include_router(outreach_router)
    app.include_router(auth_router)
    app.include_router(secure_demo_router)
    app.include_router(read_models_router)
    app.include_router(organizations_router)
    app.include_router(billing_router)
    app.include_router(audit_router)
    app.include_router(metrics_router)
    app.include_router(logs_router)
    app.include_router(branding_router)
    app.include_router(cdn_router)
    app.include_router(tenants_router)

    return app
