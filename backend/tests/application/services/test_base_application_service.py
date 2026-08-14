from typing import ClassVar

from app.application.services.application_service_result import ApplicationServiceResult
from app.application.services.base_application_service import BaseApplicationService


class _EchoService(BaseApplicationService):
    service_name: ClassVar[str] = "echo_service"

    async def echo(self, value: str) -> ApplicationServiceResult:
        async def _operation():
            return {"echo": value}

        return await self._run("echo", _operation)

    async def boom(self) -> ApplicationServiceResult:
        async def _operation():
            raise RuntimeError("kaboom")

        return await self._run("boom", _operation)


async def test_run_success_wraps_data_and_records_a_log():
    service = _EchoService()

    result = await service.echo("hi")

    assert result.success is True
    assert result.data == {"echo": "hi"}
    assert result.errors == []
    assert result.execution_time >= 0
    logs = service.list_execution_logs()
    assert len(logs) == 1
    assert "succeeded" in logs[0]


async def test_run_failure_never_raises_and_records_a_log():
    service = _EchoService()

    result = await service.boom()

    assert result.success is False
    assert result.data is None
    assert result.errors == ["kaboom"]
    logs = service.list_execution_logs()
    assert len(logs) == 1
    assert "failed" in logs[0]


async def test_execution_logs_accumulate_across_calls():
    service = _EchoService()

    await service.echo("a")
    await service.boom()
    await service.echo("b")

    assert len(service.list_execution_logs()) == 3
