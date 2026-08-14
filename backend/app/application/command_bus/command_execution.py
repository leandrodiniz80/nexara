from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.application.bus.bus_execution import BusExecution


class CommandExecution(BaseModel):
    """CommandBus's own internal record of one command dispatch — now a
    thin wrapper around the shared BusExecution, exposing the same
    command-shaped view (`command` instead of the generic `name`) that
    CommandBus's internals already relied on. Never exposed outside
    CommandBus.
    """

    model_config = ConfigDict(frozen=True)

    bus_execution: BusExecution

    @property
    def command(self) -> str:
        return self.bus_execution.name

    @property
    def started_at(self) -> datetime:
        return self.bus_execution.started_at

    @property
    def finished_at(self) -> datetime:
        return self.bus_execution.finished_at

    @property
    def duration(self) -> float:
        return self.bus_execution.duration

    @property
    def success(self) -> bool:
        return self.bus_execution.success

    @property
    def payload(self) -> Any | None:
        return self.bus_execution.payload

    @property
    def reason(self) -> str | None:
        return self.bus_execution.reason
