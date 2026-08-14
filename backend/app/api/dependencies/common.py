from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """One AsyncSession per request — FastAPI resolves this dependency once and
    reuses the same instance for every other dependency in the same request that
    also depends on it, then closes it when the request ends."""
    async with AsyncSessionLocal() as session:
        yield session


def get_request_id(request: Request) -> str:
    """Reads what RequestIdMiddleware already stamped onto request.state — routes
    that want the request_id explicitly (rather than only through ApiResponse)
    depend on this instead of reaching into `request.state` themselves."""
    return getattr(request.state, "request_id", None) or "unknown"
