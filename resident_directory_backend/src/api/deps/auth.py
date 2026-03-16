import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.api.core.security import decode_access_token
from src.api.db.models import Role, User, UserRole
from src.api.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _get_user_roles(db: Session, user_id: uuid.UUID) -> list[str]:
    role_names = (
        db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id)
        .all()
    )
    return [r[0] for r in role_names]


# PUBLIC_INTERFACE
def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    """Resolve the current authenticated user from the Bearer token."""
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or not found")

    # Attach roles list as transient attribute (handy for route logic).
    user._role_names = _get_user_roles(db, user.id)  # type: ignore[attr-defined]
    return user


# PUBLIC_INTERFACE
def require_roles(*required_roles: str):
    """FastAPI dependency factory enforcing RBAC role membership."""

    def _checker(user: User = Depends(get_current_user)) -> User:
        role_names = getattr(user, "_role_names", [])
        if not any(r in role_names for r in required_roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _checker
