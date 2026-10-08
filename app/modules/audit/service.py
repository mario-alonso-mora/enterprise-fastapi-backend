import uuid

from sqlalchemy.orm import Session

from app.modules.audit.models import AuditEvent


def record_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changed_fields: list[str],
    request_id: str,
) -> None:
    # Same transaction as the business operation.
    # Store field names only, never sensitive values.
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changed_fields=changed_fields,
            request_id=request_id,
        )
    )
