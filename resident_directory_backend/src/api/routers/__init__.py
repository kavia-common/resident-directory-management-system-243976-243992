from src.api.routers.announcements import router as announcements_router
from src.api.routers.auth import router as auth_router
from src.api.routers.messaging import router as messaging_router
from src.api.routers.residents import router as residents_router
from src.api.routers.admin import router as admin_router

__all__ = [
    "auth_router",
    "residents_router",
    "announcements_router",
    "messaging_router",
    "admin_router",
]
