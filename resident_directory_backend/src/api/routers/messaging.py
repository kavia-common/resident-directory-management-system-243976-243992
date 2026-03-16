import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.api.db.models import (
    ContactRequest,
    Message,
    MessageThread,
    MessageThreadParticipant,
    User,
)
from src.api.db.session import get_db
from src.api.deps.auth import get_current_user
from src.api.schemas.messaging import (
    ContactRequestCreate,
    ContactRequestOut,
    ContactRequestRespond,
    MessageCreate,
    MessageOut,
    MessageThreadOut,
)
from src.api.services.audit import write_audit_log

router = APIRouter(prefix="/messaging", tags=["messaging"])


def _cr_out(cr: ContactRequest) -> ContactRequestOut:
    return ContactRequestOut(
        id=cr.id,
        from_user_id=cr.from_user_id,
        to_user_id=cr.to_user_id,
        subject=cr.subject,
        initial_message=cr.initial_message,
        status=cr.status,
        responded_at=cr.responded_at,
        created_at=cr.created_at,
        updated_at=cr.updated_at,
    )


def _thread_out(db: Session, t: MessageThread) -> MessageThreadOut:
    participants = db.query(MessageThreadParticipant.user_id).filter(MessageThreadParticipant.thread_id == t.id).all()
    return MessageThreadOut(
        id=t.id,
        contact_request_id=t.contact_request_id,
        created_at=t.created_at,
        participants=[p[0] for p in participants],
    )


def _ensure_thread_participant(db: Session, thread_id: uuid.UUID, user_id: uuid.UUID) -> None:
    exists = (
        db.query(MessageThreadParticipant)
        .filter(MessageThreadParticipant.thread_id == thread_id, MessageThreadParticipant.user_id == user_id)
        .first()
    )
    if not exists:
        raise HTTPException(status_code=403, detail="Not a participant in this thread")


@router.post(
    "/contact-requests",
    response_model=ContactRequestOut,
    summary="Create contact request",
    description="Create a contact request to another user. Prevents duplicate pending requests due to DB constraint.",
)
# PUBLIC_INTERFACE
def create_contact_request(
    payload: ContactRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a contact request."""
    if payload.to_user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    cr = ContactRequest(
        from_user_id=user.id,
        to_user_id=payload.to_user_id,
        subject=payload.subject,
        initial_message=payload.initial_message,
        status="pending",
    )
    db.add(cr)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="A pending request may already exist")
    db.refresh(cr)

    write_audit_log(db, action="contact_request.create", actor=user, entity_type="contact_request", entity_id=cr.id, request=request)
    return _cr_out(cr)


@router.get(
    "/contact-requests/inbox",
    response_model=list[ContactRequestOut],
    summary="List contact requests received",
    description="List contact requests where current user is recipient.",
)
# PUBLIC_INTERFACE
def inbox(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Inbox for contact requests."""
    rows = (
        db.query(ContactRequest)
        .filter(ContactRequest.to_user_id == user.id)
        .order_by(ContactRequest.created_at.desc())
        .all()
    )
    return [_cr_out(r) for r in rows]


@router.get(
    "/contact-requests/outbox",
    response_model=list[ContactRequestOut],
    summary="List contact requests sent",
    description="List contact requests where current user is sender.",
)
# PUBLIC_INTERFACE
def outbox(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Outbox for contact requests."""
    rows = (
        db.query(ContactRequest)
        .filter(ContactRequest.from_user_id == user.id)
        .order_by(ContactRequest.created_at.desc())
        .all()
    )
    return [_cr_out(r) for r in rows]


@router.post(
    "/contact-requests/{contact_request_id}/respond",
    response_model=MessageThreadOut | ContactRequestOut,
    summary="Respond to a contact request",
    description="Recipient can accept/decline/close. Accept creates a message thread with both users.",
)
# PUBLIC_INTERFACE
def respond_to_contact_request(
    contact_request_id: uuid.UUID,
    payload: ContactRequestRespond,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Respond to a contact request."""
    cr = db.query(ContactRequest).filter(ContactRequest.id == contact_request_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Contact request not found")
    if cr.to_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only recipient may respond")

    action = payload.action.lower().strip()
    if action not in ("accepted", "declined", "closed"):
        raise HTTPException(status_code=400, detail="Invalid action")

    cr.status = action
    cr.responded_at = datetime.now(timezone.utc)
    db.add(cr)
    db.commit()
    db.refresh(cr)

    write_audit_log(
        db,
        action=f"contact_request.{action}",
        actor=user,
        entity_type="contact_request",
        entity_id=cr.id,
        request=request,
    )

    if action != "accepted":
        return _cr_out(cr)

    # Create/get thread
    thread = db.query(MessageThread).filter(MessageThread.contact_request_id == cr.id).first()
    if not thread:
        thread = MessageThread(created_by_user_id=user.id, contact_request_id=cr.id)
        db.add(thread)
        db.commit()
        db.refresh(thread)
        # Participants
        db.add(MessageThreadParticipant(thread_id=thread.id, user_id=cr.from_user_id))
        db.add(MessageThreadParticipant(thread_id=thread.id, user_id=cr.to_user_id))
        db.commit()

    return _thread_out(db, thread)


@router.get(
    "/threads",
    response_model=list[MessageThreadOut],
    summary="List my message threads",
    description="List threads where current user is a participant.",
)
# PUBLIC_INTERFACE
def list_threads(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """List threads for current user."""
    thread_ids = (
        db.query(MessageThreadParticipant.thread_id)
        .filter(MessageThreadParticipant.user_id == user.id)
        .all()
    )
    ids = [t[0] for t in thread_ids]
    if not ids:
        return []
    threads = db.query(MessageThread).filter(MessageThread.id.in_(ids)).order_by(MessageThread.created_at.desc()).all()
    return [_thread_out(db, t) for t in threads]


@router.get(
    "/threads/{thread_id}/messages",
    response_model=list[MessageOut],
    summary="List messages in thread",
    description="List messages for a thread (participants only).",
)
# PUBLIC_INTERFACE
def list_messages(thread_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """List messages in a thread."""
    _ensure_thread_participant(db, thread_id, user.id)
    msgs = db.query(Message).filter(Message.thread_id == thread_id).order_by(Message.created_at.asc()).all()
    return [
        MessageOut(id=m.id, thread_id=m.thread_id, sender_user_id=m.sender_user_id, body=m.body, created_at=m.created_at)
        for m in msgs
    ]


@router.post(
    "/threads/{thread_id}/messages",
    response_model=MessageOut,
    summary="Send message",
    description="Send a message to a thread (participants only).",
)
# PUBLIC_INTERFACE
def send_message(
    thread_id: uuid.UUID,
    payload: MessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send message."""
    _ensure_thread_participant(db, thread_id, user.id)

    msg = Message(thread_id=thread_id, sender_user_id=user.id, body=payload.body)
    db.add(msg)
    db.commit()
    db.refresh(msg)

    write_audit_log(db, action="message.send", actor=user, entity_type="message", entity_id=msg.id, request=request)

    return MessageOut(id=msg.id, thread_id=msg.thread_id, sender_user_id=msg.sender_user_id, body=msg.body, created_at=msg.created_at)
