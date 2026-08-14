import pytest

from app.platform.exceptions.platform_exceptions import ModuleNotRegisteredError
from app.platform.kernel.kernel_builder import KernelBuilder
from app.platform.kernel.platform_kernel import PlatformKernel
from app.platform.models.enums import ModuleType
from app.platform.models.platform_context import PlatformContext
from app.platform.registry.module_registry import ModuleRegistry
from app.platform.repositories.module_repository import ModuleRepository


def _kernel() -> PlatformKernel:
    return PlatformKernel(
        registry=ModuleRegistry(),
        repository=ModuleRepository(),
        context=PlatformContext(environment="test", application_version="0.1.0"),
    )


def test_register_module_returns_a_platform_module_and_stores_it_in_both_layers():
    kernel = _kernel()
    descriptor = KernelBuilder.build_descriptor(name="CRM", version="1.0.0")

    module = kernel.register_module(ModuleType.CRM, descriptor)

    assert module.module_type == ModuleType.CRM
    assert module.descriptor is descriptor
    assert kernel.registry.get(ModuleType.CRM) is module
    assert kernel.repository.get_module(ModuleType.CRM) is module


def test_get_module_returns_the_registered_module():
    kernel = _kernel()
    descriptor = KernelBuilder.build_descriptor(name="Runtime", version="1.0.0")
    kernel.register_module(ModuleType.RUNTIME, descriptor)

    module = kernel.get_module(ModuleType.RUNTIME)

    assert module.descriptor.name == "Runtime"


def test_get_module_for_unregistered_type_raises():
    kernel = _kernel()

    with pytest.raises(ModuleNotRegisteredError):
        kernel.get_module(ModuleType.RUNTIME)


def test_list_modules_returns_every_registered_module():
    kernel = _kernel()
    kernel.register_module(ModuleType.CRM, KernelBuilder.build_descriptor(name="CRM", version="1"))
    kernel.register_module(
        ModuleType.RUNTIME, KernelBuilder.build_descriptor(name="Runtime", version="1")
    )

    modules = kernel.list_modules()

    assert {m.module_type for m in modules} == {ModuleType.CRM, ModuleType.RUNTIME}


def test_is_registered_reflects_registration_state():
    kernel = _kernel()

    assert kernel.is_registered(ModuleType.CRM) is False

    kernel.register_module(ModuleType.CRM, KernelBuilder.build_descriptor(name="CRM", version="1"))

    assert kernel.is_registered(ModuleType.CRM) is True


def test_health_counts_registered_enabled_and_disabled_modules():
    kernel = _kernel()
    kernel.register_module(
        ModuleType.CRM, KernelBuilder.build_descriptor(name="CRM", version="1", enabled=True)
    )
    kernel.register_module(
        ModuleType.AI, KernelBuilder.build_descriptor(name="AI", version="1", enabled=False)
    )

    health = kernel.health()

    assert health["registered_modules"] == 2
    assert health["enabled_modules"] == 1
    assert health["disabled_modules"] == 1
    assert health["kernel_version"] == kernel.kernel_version
    assert health["platform_started_at"] == kernel.context.started_at


def test_version_returns_the_kernel_version():
    kernel = PlatformKernel(
        registry=ModuleRegistry(),
        repository=ModuleRepository(),
        context=PlatformContext(),
        kernel_version="2.3.4",
    )

    assert kernel.version() == "2.3.4"


def test_platform_kernel_never_imports_workflow_runtime_crm_or_ai():
    import app.platform.kernel.platform_kernel as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    for forbidden in ("WorkflowEngine", "RuntimeEngine", "CRMEngine", "app.ai", "AIOrchestrator"):
        assert forbidden not in source
