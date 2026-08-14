from app.platform.kernel.kernel_factory import build_default_platform_kernel
from app.platform.models.enums import ModuleType
from app.platform.registry.module_registry import ModuleRegistry
from app.platform.repositories.module_repository import ModuleRepository


def test_build_default_platform_kernel_registers_every_module_type():
    kernel = build_default_platform_kernel()

    registered = {m.module_type for m in kernel.list_modules()}
    assert registered == set(ModuleType)


def test_build_default_platform_kernel_registers_every_module_enabled_by_default():
    kernel = build_default_platform_kernel()

    health = kernel.health()

    assert health["registered_modules"] == len(ModuleType)
    assert health["enabled_modules"] == len(ModuleType)
    assert health["disabled_modules"] == 0


def test_build_default_platform_kernel_uses_the_given_environment_and_version():
    kernel = build_default_platform_kernel(environment="production", application_version="3.1.0")

    assert kernel.context.environment == "production"
    assert kernel.context.application_version == "3.1.0"


def test_build_default_platform_kernel_reuses_a_given_registry_and_repository():
    registry = ModuleRegistry()
    repository = ModuleRepository()

    kernel = build_default_platform_kernel(registry=registry, repository=repository)

    assert kernel.registry is registry
    assert kernel.repository is repository


def test_each_default_descriptor_has_a_name_matching_its_module_type():
    kernel = build_default_platform_kernel()

    workflow = kernel.get_module(ModuleType.WORKFLOW)
    assert workflow.descriptor.name == "Workflow"

    crm = kernel.get_module(ModuleType.CRM)
    assert crm.descriptor.name == "CRM"


def test_kernel_factory_never_imports_a_real_engine_or_ai_module():
    import app.platform.kernel.kernel_factory as module

    with open(module.__file__, encoding="utf-8") as source_file:
        source = source_file.read()

    for forbidden in ("WorkflowEngine", "RuntimeEngine", "CRMEngine", "app.ai", "AIOrchestrator"):
        assert forbidden not in source
