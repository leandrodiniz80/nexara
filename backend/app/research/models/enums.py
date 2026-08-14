import enum


class ResearchSource(str, enum.Enum):
    """Which provider originated a ResearchResult. One member per ResearchProvider.

    MOCK was not in the original 7-provider list — it's the deterministic, offline
    stand-in this phase's Lead Discovery Pipeline runs against (no Google/LinkedIn/AI
    integration yet), same role as app.ai.providers.mock_provider.MockProvider.
    """

    GOOGLE_MAPS = "google_maps"
    GOOGLE_BUSINESS = "google_business"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    WEBSITE = "website"
    CSV = "csv"
    MANUAL = "manual"
    MOCK = "mock"
