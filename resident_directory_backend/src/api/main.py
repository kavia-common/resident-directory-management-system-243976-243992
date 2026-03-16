from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.core.config import get_settings
from src.api.routers import (
    admin_router,
    announcements_router,
    auth_router,
    messaging_router,
    residents_router,
)

settings = get_settings()

openapi_tags = [
    {"name": "auth", "description": "Authentication and session endpoints (JWT)"},
    {"name": "residents", "description": "Resident directory and profile/privacy management"},
    {"name": "announcements", "description": "Community announcements"},
    {"name": "messaging", "description": "Contact requests and messaging threads"},
    {"name": "admin", "description": "Admin tools: import/export and audit logs"},
]

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Resident Directory Management System API.\n\n"
        "Auth: Use `POST /auth/login` (OAuth2 password flow) to obtain a Bearer token.\n"
        "Then call authenticated endpoints with `Authorization: Bearer <token>`.\n"
    ),
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", summary="Health check", tags=["auth"])
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint for uptime monitoring."""
    return {"message": "Healthy"}


@app.get("/docs/auth", summary="Auth usage help", tags=["auth"])
# PUBLIC_INTERFACE
def auth_usage_help():
    """Explain how to authenticate with this API using the built-in Swagger UI."""
    return {
        "login": {
            "endpoint": "/auth/login",
            "notes": "Use OAuth2 password flow: username=email, password=your password",
        },
        "header": "Authorization: Bearer <access_token>",
    }


app.include_router(auth_router)
app.include_router(residents_router)
app.include_router(announcements_router)
app.include_router(messaging_router)
app.include_router(admin_router)
