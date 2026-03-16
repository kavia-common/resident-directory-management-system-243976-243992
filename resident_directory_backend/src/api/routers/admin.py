import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.api.core.security import hash_password
from src.api.db.models import (
    AuditLog,
    DataExportJob,
    DataImportJob,
    ResidentProfile,
    Role,
    User,
    UserRole,
)
from src.api.db.session import get_db
from src.api.deps.auth import require_roles
from src.api.schemas.admin import (
    AuditLogOut,
    ExportJobOut,
    ExportRequest,
    ImportJobOut,
    ImportRequest,
)
from src.api.schemas.residents import PrivacySettings
from src.api.services.audit import write_audit_log

router = APIRouter(prefix="/admin", tags=["admin"])


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
    "/bootstrap-admin",
    summary="Bootstrap an admin (one-time helper)",
    description="Creates/updates the given email user and ensures they have admin role. Intended for local/dev setups.",
)
# PUBLIC_INTERFACE
def bootstrap_admin(
    email: str,
    password: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Bootstrap admin account. No auth required; rely on deployment environment to disable/remove if needed."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, password_hash=hash_password(password), is_active=True, is_verified=False)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.password_hash = hash_password(password)
        db.add(user)
        db.commit()
        db.refresh(user)

    admin_role = _get_or_create_role(db, "admin")
    existing = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == admin_role.id).first()
    if not existing:
        db.add(UserRole(user_id=user.id, role_id=admin_role.id))
        db.commit()

    write_audit_log(db, action="admin.bootstrap", actor=user, entity_type="user", entity_id=user.id, request=request)
    return {"ok": True, "user_id": str(user.id)}


@router.post(
    "/import",
    response_model=ImportJobOut,
    summary="Import residents (admin)",
    description="Admin-only: import residents from JSON rows (email/password/profile fields).",
)
# PUBLIC_INTERFACE
def import_residents(
    payload: ImportRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Import residents (synchronous)."""
    job = DataImportJob(
        requested_by_user_id=admin.id,
        source="admin_ui",
        status="running",
        total_records=len(payload.residents),
        processed_records=0,
        error_count=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    resident_role = _get_or_create_role(db, "resident")

    errors: list[str] = []
    processed = 0
    for row in payload.residents:
        try:
            existing_user = db.query(User).filter(User.email == row.email).first()
            if existing_user:
                raise ValueError("User already exists")

            user = User(email=row.email, password_hash=hash_password(row.password), is_active=True, is_verified=False)
            db.add(user)
            db.commit()
            db.refresh(user)

            db.add(UserRole(user_id=user.id, role_id=resident_role.id))
            db.commit()

            privacy = row.privacy or PrivacySettings(
                is_directory_visible=True,
                show_email=False,
                show_phone=False,
                show_unit=False,
                show_building=False,
                show_bio=True,
                show_tags=True,
            )

            profile = ResidentProfile(
                user_id=user.id,
                first_name=row.first_name,
                last_name=row.last_name,
                display_name=row.display_name,
                unit=row.unit,
                building=row.building,
                phone=row.phone,
                bio=row.bio,
                tags=row.tags or [],
                is_directory_visible=privacy.is_directory_visible,
                show_email=privacy.show_email,
                show_phone=privacy.show_phone,
                show_unit=privacy.show_unit,
                show_building=privacy.show_building,
                show_bio=privacy.show_bio,
                show_tags=privacy.show_tags,
            )
            db.add(profile)
            db.commit()

            processed += 1
            job.processed_records = processed
            db.add(job)
            db.commit()
        except Exception as exc:
            db.rollback()
            errors.append(f"{row.email}: {exc}")
            job.error_count = len(errors)
            job.processed_records = processed
            db.add(job)
            db.commit()

    job.status = "succeeded" if not errors else "failed"
    job.finished_at = datetime.now(timezone.utc)
    job.error_summary = "\n".join(errors[:50]) if errors else None
    db.add(job)
    db.commit()
    db.refresh(job)

    write_audit_log(
        db,
        action="admin.import",
        actor=admin,
        entity_type="data_import_job",
        entity_id=job.id,
        success=(job.status == "succeeded"),
        details={"errors": errors[:10]},
        request=request,
    )

    return ImportJobOut(
        id=job.id,
        status=job.status,
        total_records=job.total_records,
        processed_records=job.processed_records,
        error_count=job.error_count,
        error_summary=job.error_summary,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


@router.post(
    "/export",
    summary="Export residents (admin)",
    description="Admin-only: export residents (CSV/JSON). Returns a file response.",
)
# PUBLIC_INTERFACE
def export_residents(
    payload: ExportRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    """Export residents to CSV or JSON."""
    fmt = payload.format.lower().strip()
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="format must be csv or json")

    job = DataExportJob(requested_by_user_id=admin.id, format=fmt, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)

    profiles = db.query(ResidentProfile).order_by(ResidentProfile.last_name.asc(), ResidentProfile.first_name.asc()).all()
    job.total_records = len(profiles)
    job.status = "succeeded"
    job.finished_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()
    db.refresh(job)

    write_audit_log(db, action="admin.export", actor=admin, entity_type="data_export_job", entity_id=job.id, request=request)

    if fmt == "json":
        data = [
            {
                "id": str(p.id),
                "user_id": str(p.user_id),
                "first_name": p.first_name,
                "last_name": p.last_name,
                "display_name": p.display_name,
                "unit": p.unit,
                "building": p.building,
                "phone": p.phone,
                "email_public_override": p.email_public_override,
                "bio": p.bio,
                "tags": p.tags or [],
                "privacy": {
                    "is_directory_visible": p.is_directory_visible,
                    "show_email": p.show_email,
                    "show_phone": p.show_phone,
                    "show_unit": p.show_unit,
                    "show_building": p.show_building,
                    "show_bio": p.show_bio,
                    "show_tags": p.show_tags,
                },
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in profiles
        ]
        return {"job": ExportJobOut(**job.__dict__), "data": data}

    # CSV streaming
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "id",
            "user_id",
            "first_name",
            "last_name",
            "display_name",
            "unit",
            "building",
            "phone",
            "email_public_override",
            "bio",
            "tags",
            "is_directory_visible",
            "show_email",
            "show_phone",
            "show_unit",
            "show_building",
            "show_bio",
            "show_tags",
        ]
    )
    for p in profiles:
        writer.writerow(
            [
                str(p.id),
                str(p.user_id),
                p.first_name,
                p.last_name,
                p.display_name or "",
                p.unit or "",
                p.building or "",
                p.phone or "",
                p.email_public_override or "",
                p.bio or "",
                "|".join(p.tags or []),
                str(p.is_directory_visible),
                str(p.show_email),
                str(p.show_phone),
                str(p.show_unit),
                str(p.show_building),
                str(p.show_bio),
                str(p.show_tags),
            ]
        )
    out.seek(0)

    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="residents_export_{job.id}.csv"'},
    )


@router.get(
    "/audit-logs",
    response_model=list[AuditLogOut],
    summary="List audit logs (admin)",
    description="Admin-only: list audit log entries in reverse chronological order.",
)
# PUBLIC_INTERFACE
def list_audit_logs(db: Session = Depends(get_db), admin: User = Depends(require_roles("admin"))):
    """List audit logs."""
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500).all()
    return [
        AuditLogOut(
            id=r.id,
            actor_user_id=r.actor_user_id,
            action=r.action,
            entity_type=r.entity_type,
            entity_id=r.entity_id,
            success=r.success,
            details=r.details or {},
            created_at=r.created_at,
        )
        for r in rows
    ]
