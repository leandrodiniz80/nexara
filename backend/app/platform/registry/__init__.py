from app.platform.registry.module_descriptor import ModuleDescriptor

__all__ = ["ModuleDescriptor", "ModuleRegistry"]


def __getattr__(name: str):
    """ModuleRegistry is resolved lazily (PEP 562) rather than imported eagerly
    above: ModuleRegistry itself imports PlatformModule from app.platform.models,
    and PlatformModule imports ModuleDescriptor from this package. Eagerly
    importing ModuleRegistry here forces that back-import to run while
    platform_module.py is still mid-execution (whenever something reaches this
    package via PlatformModule's own import of ModuleDescriptor), causing a
    circular-import ImportError. Deferring it to first access breaks the cycle
    without changing what's importable from this package.
    """
    if name == "ModuleRegistry":
        from app.platform.registry.module_registry import ModuleRegistry

        return ModuleRegistry

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
