from typing import Callable, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Registry(BaseModel, Generic[T]):
    """The platform's generic, frozen registry — pure lookup, nothing else.
    Knows no domain: not Commands, not Queries, not Modules. Every mutation
    (`register()`/`register_many()`) returns a NEW Registry, never edits
    this one in place.

    `key` extracts the identifying name from each item, supplied once at
    construction — different item types identify themselves differently
    (a plain field, a method call, or anything else), so this registry
    never assumes either shape.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    items: tuple[T, ...] = Field(default_factory=tuple)
    key: Callable[[T], str]

    def register(self, item: T) -> "Registry[T]":
        return Registry(items=self.items + (item,), key=self.key)

    def register_many(self, items: list[T]) -> "Registry[T]":
        return Registry(items=self.items + tuple(items), key=self.key)

    def list(self) -> list[T]:
        return list(self.items)

    def find(self, name: str) -> T | None:
        for item in self.items:
            if self.key(item) == name:
                return item
        return None

    def exists(self, name: str) -> bool:
        return self.find(name) is not None
