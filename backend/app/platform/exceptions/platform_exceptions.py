from typing import TYPE_CHECKING

from app.platform.exceptions.base import PlatformError

if TYPE_CHECKING:
    from app.platform.models.enums import ModuleType


class ModuleNotRegisteredError(PlatformError):
    """Raised when the Kernel is asked for a ModuleType no descriptor was ever
    registered for."""

    def __init__(self, module_type: "ModuleType") -> None:
        self.module_type = module_type
        super().__init__(f"No module registered for ModuleType.{module_type.name}.")
