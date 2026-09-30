import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.services.leads.workday_engine import maybe_notify_performance_alert


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


def _db(rows):
    return Mock(execute=AsyncMock(return_value=_Result(rows)), add=Mock())


async def _notify(db):
    return await maybe_notify_performance_alert(
        db, organization_id="org", user_email="a@b.com", message="x", now=datetime.now(UTC)
    )


@pytest.mark.asyncio
async def test_duplicate_alerts_do_not_raise_and_skip_new_alert():
    # Two rows already match (the concurrent-request race) — must not raise.
    db = _db([uuid.uuid4(), uuid.uuid4()])
    assert await _notify(db) is False
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_no_recent_alert_stages_one():
    db = _db([])
    assert await _notify(db) is True
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_dedup_check_is_limited_to_one_row():
    db = _db([])
    await _notify(db)
    stmt = db.execute.call_args.args[0]
    assert stmt._limit_clause is not None
