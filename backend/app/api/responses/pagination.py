from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

_MAX_PAGE_SIZE = 100


class PageRequest(BaseModel):
    """Pure input DTO — no business rule, just bounds so a caller can't ask for
    page_size=1000000. Nothing here decides what "page 1" of any given list means;
    that's each route's own concern."""

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=_MAX_PAGE_SIZE)


class PageMetadata(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class Page(BaseModel, Generic[T]):
    items: list[T]
    metadata: PageMetadata
