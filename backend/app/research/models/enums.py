import enum


class ResearchSource(str, enum.Enum):
    """Which provider originated a ResearchResult. One member per ResearchProvider."""

    GOOGLE_MAPS = "google_maps"
    GOOGLE_BUSINESS = "google_business"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    WEBSITE = "website"
    CSV = "csv"
    MANUAL = "manual"
