from app.crm.services.action_planning_service import ActionPlanningService


def build_default_action_planning_service() -> ActionPlanningService:
    """Composition root for this service. ActionPlanningService has no
    injected collaborator at all — it is a pure, stateless calculator over
    whatever CRMOpportunity/NextActionResult/activity history its caller
    already has — so this factory exists purely for consistency with every
    other module's `build_default_*` composition root, not because there is
    anything to wire.
    """
    return ActionPlanningService()
