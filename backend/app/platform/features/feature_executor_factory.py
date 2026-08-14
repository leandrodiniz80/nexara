from app.platform.features.feature_executor import FeatureExecutor
from app.platform.features.feature_manager_factory import build_default_feature_manager


def build_default_feature_executor() -> FeatureExecutor:
    """Composition root for this executor. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_feature_manager()`, and wires it into a
    FeatureExecutor — nothing else.
    """
    return FeatureExecutor(manager=build_default_feature_manager())
