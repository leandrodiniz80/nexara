from app.platform.models.enums import ModuleType
from app.platform.models.platform_module import PlatformModule
from app.platform.registry.module_descriptor import ModuleDescriptor
from app.platform.repositories.module_repository import ModuleRepository


def _module(module_type: ModuleType, **overrides) -> PlatformModule:
    defaults = dict(name="CRM", version="1.0.0")
    defaults.update(overrides)
    return PlatformModule(module_type=module_type, descriptor=ModuleDescriptor(**defaults))


def test_save_and_get_module_round_trip():
    repository = ModuleRepository()
    module = _module(ModuleType.CRM)

    repository.save_module(module)

    assert repository.get_module(ModuleType.CRM) is module


def test_get_module_for_unknown_type_returns_none():
    repository = ModuleRepository()

    assert repository.get_module(ModuleType.CRM) is None


def test_save_module_overwrites_the_same_type():
    repository = ModuleRepository()
    first = _module(ModuleType.CRM, version="1.0.0")
    second = _module(ModuleType.CRM, version="2.0.0")
    repository.save_module(first)

    repository.save_module(second)

    assert repository.get_module(ModuleType.CRM) is second


def test_list_modules_returns_every_saved_module():
    repository = ModuleRepository()
    crm = _module(ModuleType.CRM, name="CRM")
    runtime = _module(ModuleType.RUNTIME, name="Runtime")
    repository.save_module(crm)
    repository.save_module(runtime)

    modules = repository.list_modules()

    assert {m.module_type for m in modules} == {ModuleType.CRM, ModuleType.RUNTIME}
