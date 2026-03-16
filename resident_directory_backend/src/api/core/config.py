import os
from dataclasses import dataclass


def _get_env(name: str, default: str | None = None) -> str | None:
    """Internal helper to read environment variables safely."""
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    # Database (provided by the database container)
    postgres_url: str

    # Security
    jwt_secret: str
    jwt_algorithm: str
    access_token_exp_minutes: int

    # CORS
    cors_allow_origins: list[str]

    # App
    app_name: str
    app_version: str


# PUBLIC_INTERFACE
def get_settings() -> Settings:
    """Load application settings from environment variables.

    Required env vars:
    - POSTGRES_URL: SQLAlchemy-compatible database URL (e.g. postgresql+psycopg://...)
    - JWT_SECRET: secret used to sign JWT access tokens

    Optional env vars:
    - JWT_ALGORITHM (default: HS256)
    - ACCESS_TOKEN_EXPIRE_MINUTES (default: 60)
    - CORS_ALLOW_ORIGINS (default: "*") comma-separated list
    - APP_NAME, APP_VERSION
    """
    postgres_url = _get_env("POSTGRES_URL")
    if not postgres_url:
        raise RuntimeError(
            "Missing required env var POSTGRES_URL. "
            "It is provided by the resident_directory_database container."
        )

    jwt_secret = _get_env("JWT_SECRET")
    if not jwt_secret:
        raise RuntimeError(
            "Missing required env var JWT_SECRET. "
            "Please provide a strong secret via environment configuration."
        )

    jwt_algorithm = _get_env("JWT_ALGORITHM", "HS256") or "HS256"
    exp_raw = _get_env("ACCESS_TOKEN_EXPIRE_MINUTES", "60") or "60"
    try:
        access_token_exp_minutes = int(exp_raw)
    except ValueError as exc:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer") from exc

    cors_raw = _get_env("CORS_ALLOW_ORIGINS", "*") or "*"
    cors_allow_origins = ["*"] if cors_raw.strip() == "*" else [o.strip() for o in cors_raw.split(",") if o.strip()]

    return Settings(
        postgres_url=postgres_url,
        jwt_secret=jwt_secret,
        jwt_algorithm=jwt_algorithm,
        access_token_exp_minutes=access_token_exp_minutes,
        cors_allow_origins=cors_allow_origins,
        app_name=_get_env("APP_NAME", "Resident Directory Backend") or "Resident Directory Backend",
        app_version=_get_env("APP_VERSION", "1.0.0") or "1.0.0",
    )
