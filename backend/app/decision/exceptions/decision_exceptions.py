from typing import TYPE_CHECKING

from app.decision.exceptions.base import DecisionError

if TYPE_CHECKING:
    from app.decision.models.enums import DecisionType


class NoStrategyFoundError(DecisionError):
    """Raised when DecisionEngine has no Strategy registered that supports a
    given DecisionType."""

    def __init__(self, decision_type: "DecisionType") -> None:
        self.decision_type = decision_type
        super().__init__(f"No strategy registered that supports DecisionType.{decision_type.name}.")


class NoCandidateOptionsError(DecisionError):
    """Raised when the Strategy that supports a DecisionType returns no
    DecisionOptions at all — there is nothing to select from."""

    def __init__(self, decision_type: "DecisionType") -> None:
        self.decision_type = decision_type
        super().__init__(
            f"Strategy for DecisionType.{decision_type.name} returned no candidate options."
        )
