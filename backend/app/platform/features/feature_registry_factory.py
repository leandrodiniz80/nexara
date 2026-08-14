from app.platform.features.feature_registry import FeatureRegistry


def build_default_feature_registry() -> FeatureRegistry:
    """Composition root for this registry. Returns an empty registry — no
    concrete Feature exists yet to register.
    """
    return FeatureRegistry()
