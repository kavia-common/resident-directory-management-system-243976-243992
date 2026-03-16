from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.api.core.security import create_access_token, hash_password, verify_password
from src.api.db.models import ResidentProfile, Role, User, UserRole
from src.api.db.session import get_db
from src.api.deps.auth import get_current_user
from src.api.schemas.auth import RegisterRequest, Token
from src.api.services.audit import write_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_or_create_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if role:
        return role
    role = Role(name=role_name, description=f"Auto-created role {role_name}")
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.post(
    "/register",
    response_model=Token,
    summary="Register a new resident user",
    description="Creates a user + resident profile with default privacy settings, and returns an access token.",
    status_code=201,
)
# PUBLIC_INTERFACE
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> Token:
    """Register a new resident user and return an access token."""
    existing = db.query(User).filter(User.email == str(payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        is_active=True,
        is_verified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    resident_role = _get_or_create_role(db, "resident")
    db.add(UserRole(user_id=user.id, role_id=resident_role.id))
    db.commit()

    # Create profile with conservative privacy defaults (not exposing phone/email/unit/building)
    profile = ResidentProfile(
        user_id=user.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        display_name=payload.display_name,
        is_directory_visible=True,
        show_email=False,
        show_phone=False,
        show_unit=False,
        show_building=False,
        show_bio=True,
        show_tags=True,
        tags=[],
    )
    db.add(profile)
    db.commit()

    write_audit_log(db, action="user.register", actor=user, entity_type="user", entity_id=user.id, request=request)

    token = create_access_token(str(user.id), roles=["resident"])
    return Token(access_token=token, token_type="bearer")


@router.post(
    "/login",
    response_model=Token,
    summary="Login",
    description="OAuth2 password flow. Provide username=email and password. Returns access token.",
)
# PUBLIC_INTERFACE
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    request: Request | None = None,
    db: Session = Depends(get_db),
) -> Token:
    """Login using email+password, returning an access token."""
    email = form.username
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(form.password, user.password_hash) or not user.is_active:
        if request:
            write_audit_log(db, action="user.login", actor=None, success=False, details={"email": email}, request=request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    # roles
    role_names = (
        db.query(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user.id)
        .all()
    )
    roles = [r[0] for r in role_names] or ["resident"]

    if request:
        write_audit_log(db, action="user.login", actor=user, entity_type="user", entity_id=user.id, request=request)

    token = create_access_token(str(user.id), roles=roles)
    return Token(access_token=token, token_type="bearer")


@router.get(
    "/me",
    summary="Get current user",
    description="Returns the current authenticated user's basic identity and roles.",
)
# PUBLIC_INTERFACE
def me(user: User = Depends(get_current_user)):
    """Return current user identity and role list."""
    return {"id": str(user.id), "email": user.email, "roles": getattr(user, "_role_names", [])}
