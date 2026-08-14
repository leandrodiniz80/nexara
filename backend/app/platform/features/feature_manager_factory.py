from app.platform.features.feature_manager import FeatureManager
from app.platform.features.feature_registry_factory import build_default_feature_registry


def build_default_feature_manager() -> FeatureManager:
    """Composition root for this manager. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_feature_registry()`, and wires it into a
    FeatureManager — nothing else.
    """
    return FeatureManager(registry=build_default_feature_registry())
