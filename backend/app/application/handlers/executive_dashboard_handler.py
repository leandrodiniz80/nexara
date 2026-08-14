from typing import Any

from app.application.handlers.command_handler import CommandHandler
from app.application.public.public_use_case_service import PublicUseCaseService


class ExecutiveDashboardHandler(CommandHandler):
    """The platform's first concrete Command Handler — the exclusive
    adapter between CommandBus and PublicUseCaseService for the
    "executive_dashboard" command. It knows exclusively
    PublicUseCaseService: nothing about CRM, Runtime, Workflow,
    PlatformInterface, Presentation, or Contracts.

    `handle()` never transforms or interprets `payload`, never
    recalculates anything: it only unpacks the `(dashboard, report, kpis)`
    tuple exactly as PublicUseCaseService.execute() already requires, and
    delegates entirely to it.
    """

    def __init__(self, public_use_case_service: PublicUseCaseService) -> None:
        self._public_use_case_service = public_use_case_service

    def command_name(self) -> str:
        return "executive_dashboard"

    def handle(self, payload: Any) -> Any:
        dashboard, report, kpis = payload
        return self._public_use_case_service.execute(dashboard, report, kpis)
