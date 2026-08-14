from typing import Dict, List, Tuple, TypedDict

from app.platform.bootstrap.platform_service_catalog import PlatformServiceCatalog
from app.platform.bootstrap.platform_service_descriptor import PlatformServiceDescriptor


class PlatformReadModels(TypedDict):
    catalog: PlatformServiceCatalog
    services: List[PlatformServiceDescriptor]
    service_names: Tuple[str, ...]
    service_map: Dict[str, object]
