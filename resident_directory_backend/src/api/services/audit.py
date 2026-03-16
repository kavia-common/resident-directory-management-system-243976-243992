from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from src.api.db.models import AuditLog, User


# PUBLIC_INTERFACE
def write_audit_log(
    db: Session,
    *,
    action: str,
    actor: User | None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    success: bool = True,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Persist an audit log entry.

    This is intentionally simple and synchronous, and can be expanded later
    (e.g., async queue, richer metadata).
    """
    log = AuditLog(
        actor_user_id=(actor.id if actor else None),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        success=success,
        request_id=(request.headers.get("x-request-id") if request else None) if request else None,
        ip_address=(request.client.host if request and request.client else None) if request else None,
        user_agent=(request.headers.get("user-agent") if request else None) if request else None,
        details=details or {},
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
