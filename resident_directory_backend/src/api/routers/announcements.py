import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from src.api.db.models import Announcement, User
from src.api.db.session import get_db
from src.api.deps.auth import get_current_user, require_roles
from src.api.schemas.announcements import AnnouncementCreate, AnnouncementOut, AnnouncementUpdate
from src.api.services.audit import write_audit_log

router = APIRouter(prefix="/announcements", tags=["announcements"])


def _to_out(a: Announcement) -> AnnouncementOut:
    return AnnouncementOut(
        id=a.id,
        title=a.title,
        body=a.body,
        created_by_user_id=a.created_by_user_id,
        is_published=a.is_published,
        published_at=a.published_at,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get(
    "/",
    response_model=list[AnnouncementOut],
    summary="List announcements",
    description="List published announcements. Admins may include unpublished via include_unpublished=true.",
)
# PUBLIC_INTERFACE
def list_announcements(
    include_unpublished: bool = Query(False, description="Admins only: include unpublished announcements"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List announcements."""
    q = db.query(Announcement)
    if include_unpublished and "admin" in getattr(user, "_role_names", []):
        pass
    else:
        q = q.filter(Announcement.is_published.is_(True))
    q = q.order_by((Announcement.published_at.desc().nullslast()), Announcement.created_at.desc())
    return [_to_out(a) for a in q.all()]


@router.post(
    "/",
    response_model=AnnouncementOut,
    summary="Create announcement (admin)",
    description="Admin-only: create announcement.",
)
# PUBLIC_INTERFACE
def create_announcement(
    payload: AnnouncementCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Create announcement."""
    now = datetime.now(timezone.utc)
    a = Announcement(
        title=payload.title,
        body=payload.body,
        created_by_user_id=admin.id,
        is_published=payload.is_published,
        published_at=(now if payload.is_published else None),
    )
    db.add(a)
    db.commit()
    db.refresh(a)

    write_audit_log(db, action="announcement.create", actor=admin, entity_type="announcement", entity_id=a.id, request=request)
    return _to_out(a)


@router.patch(
    "/{announcement_id}",
    response_model=AnnouncementOut,
    summary="Update announcement (admin)",
    description="Admin-only: update announcement.",
)
# PUBLIC_INTERFACE
def update_announcement(
    announcement_id: uuid.UUID,
    payload: AnnouncementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Update announcement."""
    a = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")

    data = payload.model_dump(exclude_unset=True)
    if "is_published" in data:
        if data["is_published"] and not a.published_at:
            a.published_at = datetime.now(timezone.utc)
        if not data["is_published"]:
            a.published_at = None

    for k, v in data.items():
        setattr(a, k, v)

    db.add(a)
    db.commit()
    db.refresh(a)

    write_audit_log(db, action="announcement.update", actor=admin, entity_type="announcement", entity_id=a.id, request=request)
    return _to_out(a)


@router.delete(
    "/{announcement_id}",
    summary="Delete announcement (admin)",
    description="Admin-only: delete announcement.",
)
# PUBLIC_INTERFACE
def delete_announcement(
    announcement_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Delete announcement."""
    a = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")

    db.delete(a)
    db.commit()

    write_audit_log(db, action="announcement.delete", actor=admin, entity_type="announcement", entity_id=announcement_id, request=request)
    return {"ok": True}
