from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from src.api.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# PUBLIC_INTERFACE
def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(password)


# PUBLIC_INTERFACE
def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    return pwd_context.verify(password, password_hash)


# PUBLIC_INTERFACE
def create_access_token(subject: str, roles: list[str]) -> str:
    """Create a signed JWT access token.

    Args:
        subject: user id as string
        roles: list of role names

    Returns:
        Encoded JWT token.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.access_token_exp_minutes)
    payload = {"sub": subject, "roles": roles, "iat": int(now.timestamp()), "exp": int(exp.timestamp())}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# PUBLIC_INTERFACE
def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token, raising jwt exceptions on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
