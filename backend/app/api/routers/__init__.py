from app.api.routers.health import router as health_router
from app.api.routers.missions import router as missions_router
from app.api.routers.outreach import router as outreach_router
from app.api.routers.prospects import router as prospects_router
from app.api.routers.workspace import router as workspace_router

__all__ = [
    "health_router",
    "missions_router",
    "prospects_router",
    "workspace_router",
    "outreach_router",
]
