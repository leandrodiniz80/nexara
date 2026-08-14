from app.platform.bootstrap.platform_read_models import PlatformReadModels

_V2_MAX = 1000


def get_read_models_v1(data: PlatformReadModels) -> PlatformReadModels:
    return _apply_v1(data)


def _apply_v1(data: PlatformReadModels) -> PlatformReadModels:
    return data


def get_read_models_v2(
    data: PlatformReadModels,
    registry: dict,
    counter_ref: list,
    meta_registry: dict | None = None,
) -> PlatformReadModels:
    return _apply_v2(data, registry, counter_ref, meta_registry)


def _apply_v2(
    data: PlatformReadModels,
    registry: dict,
    counter_ref: list,
    meta_registry: dict | None = None,
) -> PlatformReadModels:
    counter_ref[0] += 1
    registry[id(data)] = counter_ref[0]

    if len(registry) > _V2_MAX:
        registry.clear()

    transformed = _transform_v2(data)

    if meta_registry is not None:
        meta_registry[id(data)] = {
            "version": "v2",
            "processed": True,
            "normalized": True,
        }

        if len(meta_registry) > _V2_MAX:
            meta_registry.clear()

    return transformed


def _transform_v2(data: PlatformReadModels) -> PlatformReadModels:
    normalized = {}

    for k, v in data.items():
        normalized[k.lower()] = v

    return normalized


def get_v2_meta(data: PlatformReadModels, meta_registry: dict) -> dict | None:
    return meta_registry.get(id(data))


def is_v2(data: PlatformReadModels, registry: dict) -> bool:
    return id(data) in registry


def compare_v1_v2(v1: dict, v2: dict) -> dict:
    all_keys = set(v1.keys()) | set(v2.keys())

    return {
        "same_keys": set(v1.keys()) == set(v2.keys()),
        "same_length": len(v1) == len(v2),
        "differences": [k for k in all_keys if v1.get(k) != v2.get(k)],
    }
