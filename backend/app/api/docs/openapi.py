API_TITLE = "Elevel Prospect AI"
API_VERSION = "v1"
API_DESCRIPTION = "AI Sales Prospecting Platform"

OPENAPI_TAGS = [
    {"name": "Health", "description": "Liveness, version and uptime."},
    {
        "name": "Mission",
        "description": "Start, pause, resume, cancel and check the status of a prospecting "
        "mission — the entry point for the platform's full Research -> Qualification -> "
        "Outreach flow.",
    },
    {
        "name": "Workspace",
        "description": "Read-only, already-aggregated views built for a Frontend — never "
        "recalculates anything, only assembles what already exists.",
    },
    {
        "name": "Prospects",
        "description": "Qualify a prospect and manage the commercial assets generated for it.",
    },
    {
        "name": "Outreach",
        "description": "Generate, submit, approve and reject commercial assets directly, "
        "independent of any specific prospect flow.",
    },
    {
        "name": "Auth",
        "description": "Register, login, logout and inspect the current session — token "
        "issued on login must be sent as `Authorization: Bearer <token>` on every "
        "subsequent authenticated request.",
    },
    {
        "name": "Security",
        "description": "Smoke-test endpoints proving the authentication/role/permission "
        "guards work end-to-end over HTTP.",
    },
    {
        "name": "Read Models",
        "description": "Read-only summary of the platform's service catalog — a safe, "
        "serializable subset of the internal composition-root read models.",
    },
    {
        "name": "Organizations",
        "description": "Multi-tenant context — every user belongs to exactly one "
        "organization, and cannot see or act on another organization's data.",
    },
    {
        "name": "Billing",
        "description": "Plan and usage-limit management — no payment provider integrated "
        "yet, this only structures plans/limits/usage tracking.",
    },
    {
        "name": "Audit",
        "description": "Read-only trail of who did what, when and in which organization — "
        "owner/admin only. Never contains passwords, hashes, salts or tokens.",
    },
    {
        "name": "Metrics",
        "description": "Aggregated counters and timings for platform operations — "
        "owner/admin only. Opt-in: empty unless metrics collection is configured.",
    },
    {
        "name": "Logs",
        "description": "Structured log trail (level, message, correlation ID) for "
        "platform operations and HTTP tracing — owner/admin only. Opt-in: empty "
        "unless log collection is configured.",
    },
    {
        "name": "Branding",
        "description": "Nexara design tokens (colors, typography, spacing) for any "
        "frontend to consume — public, no auth required.",
    },
]
