from app.sales_intelligence.schemas.ranked_item import RankedItem


class RankingEngine:
    """Sorts RankedItems by CommercialScore.total_score, highest first.

    rank_companies()/rank_prospects()/rank_campaigns() are semantic aliases over the
    same sort_by_score() — the sorting logic genuinely doesn't differ by what's being
    ranked, and RankedItem.reference is opaque on purpose (see its own docstring): this
    module has no idea what a Company/Prospect/Campaign actually is, only that each one
    came with a CommercialScore attached.
    """

    def sort_by_score(self, items: list[RankedItem]) -> list[RankedItem]:
        return sorted(items, key=lambda item: item.score.total_score, reverse=True)

    def rank_companies(self, items: list[RankedItem]) -> list[RankedItem]:
        return self.sort_by_score(items)

    def rank_prospects(self, items: list[RankedItem]) -> list[RankedItem]:
        return self.sort_by_score(items)

    def rank_campaigns(self, items: list[RankedItem]) -> list[RankedItem]:
        return self.sort_by_score(items)
