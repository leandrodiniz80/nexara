import uuid

from app.outreach.models.asset_template import AssetTemplate


class TemplateRepository:
    """In-memory store of AssetTemplates — no database, no migration requested for
    this module (same reasoning as every other in-memory repository in this codebase:
    Research's ResearchResultRepository, Jobs' JobRepository)."""

    def __init__(self) -> None:
        self._templates: dict[uuid.UUID, AssetTemplate] = {}

    def add(self, template: AssetTemplate) -> AssetTemplate:
        self._templates[template.id] = template
        return template

    def get_by_id(self, template_id: uuid.UUID) -> AssetTemplate | None:
        return self._templates.get(template_id)

    def list_all(self) -> list[AssetTemplate]:
        return list(self._templates.values())

    def list_by_category(self, category: str) -> list[AssetTemplate]:
        return [t for t in self._templates.values() if t.category == category]

    def get_active_by_category(self, category: str) -> AssetTemplate | None:
        for template in self._templates.values():
            if template.category == category and template.active:
                return template
        return None
