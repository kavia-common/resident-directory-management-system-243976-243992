import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.api.db.models import ResidentProfile, User
from src.api.db.session import get_db
from src.api.deps.auth import get_current_user, require_roles
from src.api.schemas.residents import (
    PrivacySettings,
    PrivacyUpdate,
    ResidentDirectoryCard,
    ResidentProfileAdminView,
    ResidentProfileCreate,
    ResidentProfileUpdate,
)
from src.api.services.audit import write_audit_log

router = APIRouter(prefix="/residents", tags=["residents"])


def _privacy_from_model(p: ResidentProfile) -> PrivacySettings:
    return PrivacySettings(
        is_directory_visible=p.is_directory_visible,
        show_email=p.show_email,
        show_phone=p.show_phone,
        show_unit=p.show_unit,
        show_building=p.show_building,
        show_bio=p.show_bio,
        show_tags=p.show_tags,
    )


def _apply_directory_privacy(p: ResidentProfile, owner_user: User) -> ResidentDirectoryCard:
    display_name = p.display_name or f"{p.first_name} {p.last_name}".strip()
    return ResidentDirectoryCard(
        id=p.id,
        display_name=display_name,
        unit=p.unit if p.show_unit else None,
        building=p.building if p.show_building else None,
        email=(p.email_public_override or owner_user.email) if p.show_email else None,
        phone=p.phone if p.show_phone else None,
        bio=p.bio if p.show_bio else None,
        tags=p.tags if p.show_tags else [],
    )


@router.get(
    "/directory",
    response_model=list[ResidentDirectoryCard],
    summary="Search resident directory",
    description="Search and filter resident profiles with privacy controls applied.",
)
# PUBLIC_INTERFACE
def directory_search(
    q: str | None = Query(None, description="Search query (name/unit/building/tag)"),
    tag: str | None = Query(None, description="Filter by tag"),
    building: str | None = Query(None, description="Filter by building"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Search directory visible profiles and return privacy-filtered cards."""
    query = db.query(ResidentProfile, User).join(User, User.id == ResidentProfile.user_id).filter(ResidentProfile.is_directory_visible.is_(True))

    if building:
        query = query.filter(ResidentProfile.building == building)
    if tag:
        query = query.filter(ResidentProfile.tags.any(tag))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ResidentProfile.first_name.ilike(like),
                ResidentProfile.last_name.ilike(like),
                ResidentProfile.display_name.ilike(like),
                ResidentProfile.unit.ilike(like),
                ResidentProfile.building.ilike(like),
            )
        )

    results = query.order_by(ResidentProfile.last_name.asc(), ResidentProfile.first_name.asc()).all()
    return [_apply_directory_privacy(p, u) for (p, u) in results]


@router.get(
    "/me/profile",
    summary="Get my resident profile (full)",
    description="Return the authenticated user's full profile including privacy settings.",
)
# PUBLIC_INTERFACE
def get_my_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ResidentProfileAdminView:
    """Get current user's profile."""
    profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ResidentProfileAdminView(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        display_name=profile.display_name,
        unit=profile.unit,
        building=profile.building,
        phone=profile.phone,
        email_public_override=profile.email_public_override,
        bio=profile.bio,
        tags=profile.tags or [],
        privacy=_privacy_from_model(profile),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.patch(
    "/me/profile",
    summary="Update my profile",
    description="Update the authenticated user's profile fields (not privacy).",
)
# PUBLIC_INTERFACE
def update_my_profile(
    payload: ResidentProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResidentProfileAdminView:
    """Update current user's profile."""
    profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    db.add(profile)
    db.commit()
    db.refresh(profile)

    write_audit_log(db, action="profile.update", actor=user, entity_type="resident_profile", entity_id=profile.id, request=request)

    return get_my_profile(db=db, user=user)


@router.patch(
    "/me/privacy",
    summary="Update my privacy settings",
    description="Update privacy flags for directory visibility and attribute exposure.",
)
# PUBLIC_INTERFACE
def update_my_privacy(
    payload: PrivacyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update current user's privacy settings."""
    profile = db.query(ResidentProfile).filter(ResidentProfile.user_id == user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for field, value in payload.model_dump().items():
        setattr(profile, field, value)

    db.add(profile)
    db.commit()
    db.refresh(profile)

    write_audit_log(db, action="profile.privacy.update", actor=user, entity_type="resident_profile", entity_id=profile.id, request=request)
    return {"ok": True, "privacy": _privacy_from_model(profile).model_dump()}


@router.post(
    "/",
    response_model=ResidentProfileAdminView,
    summary="Admin create resident profile",
    description="Admin-only: create a profile for an existing user_id and set privacy.",
)
# PUBLIC_INTERFACE
def admin_create_profile(
    payload: ResidentProfileCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Admin create resident profile bound to an existing user."""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(ResidentProfile).filter(ResidentProfile.user_id == payload.user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already has a profile")

    profile = ResidentProfile(
        user_id=payload.user_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        display_name=payload.display_name,
        unit=payload.unit,
        building=payload.building,
        phone=payload.phone,
        email_public_override=payload.email_public_override,
        bio=payload.bio,
        tags=payload.tags or [],
        is_directory_visible=payload.privacy.is_directory_visible,
        show_email=payload.privacy.show_email,
        show_phone=payload.privacy.show_phone,
        show_unit=payload.privacy.show_unit,
        show_building=payload.privacy.show_building,
        show_bio=payload.privacy.show_bio,
        show_tags=payload.privacy.show_tags,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    write_audit_log(db, action="admin.profile.create", actor=admin, entity_type="resident_profile", entity_id=profile.id, request=request)

    return ResidentProfileAdminView(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        display_name=profile.display_name,
        unit=profile.unit,
        building=profile.building,
        phone=profile.phone,
        email_public_override=profile.email_public_override,
        bio=profile.bio,
        tags=profile.tags or [],
        privacy=_privacy_from_model(profile),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.get(
    "/{profile_id}",
    response_model=ResidentProfileAdminView,
    summary="Admin get resident profile",
    description="Admin-only: get full resident profile by profile id.",
)
# PUBLIC_INTERFACE
def admin_get_profile(
    profile_id: uuid.UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Admin get full profile."""
    profile = db.query(ResidentProfile).filter(ResidentProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    return ResidentProfileAdminView(
        id=profile.id,
        user_id=profile.user_id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        display_name=profile.display_name,
        unit=profile.unit,
        building=profile.building,
        phone=profile.phone,
        email_public_override=profile.email_public_override,
        bio=profile.bio,
        tags=profile.tags or [],
        privacy=_privacy_from_model(profile),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.delete(
    "/{profile_id}",
    summary="Admin delete resident profile",
    description="Admin-only: delete a resident profile (user remains).",
)
# PUBLIC_INTERFACE
def admin_delete_profile(
    profile_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Admin delete profile."""
    profile = db.query(ResidentProfile).filter(ResidentProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    db.delete(profile)
    db.commit()

    write_audit_log(db, action="admin.profile.delete", actor=admin, entity_type="resident_profile", entity_id=profile_id, request=request)
    return {"ok": True}
