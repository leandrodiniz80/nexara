from pydantic import BaseModel, ConfigDict, Field

from app.platform.modules.composite_platform_module import CompositePlatformModule
from app.platform.modules.platform_module import PlatformModule
from app.shared.registry.registry import Registry


class ModuleRegistry(BaseModel):
    """The platform's frozen registry of PlatformModules — pure lookup,
    plus the one place authorized to compose every registered module into
    a single CompositePlatformModule via `composite()`. It never resolves
    a module's stages itself, never knows any concrete module's domain,
    and never mutates in place. `register()`/`register_many()` always
    return a new ModuleRegistry with the given module(s) appended to the
    end of the previous, unedited list. `modules` remains the exact same
    public field it always was; every other method is now implemented by
    encapsulating a generic Registry[PlatformModule].
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    modules: tuple[PlatformModule, ...] = Field(default_factory=tuple)

    def _as_registry(self) -> Registry[PlatformModule]:
        return Registry(items=self.modules, key=lambda module: module.name())

    def register(self, module: PlatformModule) -> "ModuleRegistry":
        return ModuleRegistry(modules=tuple(self._as_registry().register(module).list()))

    def register_many(self, modules: list[PlatformModule]) -> "ModuleRegistry":
        return ModuleRegistry(
            modules=tuple(self._as_registry().register_many(modules).list())
        )

    def list(self) -> list[PlatformModule]:
        return self._as_registry().list()

    def find(self, name: str) -> PlatformModule | None:
        return self._as_registry().find(name)

    def exists(self, name: str) -> bool:
        return self._as_registry().exists(name)

    def composite(self) -> PlatformModule:
        return CompositePlatformModule(self.list())
