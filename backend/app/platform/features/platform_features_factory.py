from app.platform.features.feature_executor_factory import build_default_feature_executor
from app.platform.features.platform_features import PlatformFeatures


def build_default_platform_features() -> PlatformFeatures:
    """Composition root for this facade. Builds its one collaborator
    exclusively through its own official factory,
    `build_default_feature_executor()`, and wires it into a
    PlatformFeatures — nothing else.
    """
    return PlatformFeatures(executor=build_default_feature_executor())
