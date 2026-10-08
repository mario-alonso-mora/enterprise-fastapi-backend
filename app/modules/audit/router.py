from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.modules.audit.models import AuditEvent
from app.modules.audit.schemas import AuditEventPage
from app.modules.users.models import User

router = APIRouter(prefix="/audit-events", tags=["Audit"])


@router.get("", response_model=AuditEventPage)
def list_audit_events(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    scope = AuditEvent.organization_id == admin.organization_id

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(scope)) or 0

    items = list(
        db.scalars(
            select(AuditEvent)
            .where(scope)
            .order_by(
                AuditEvent.created_at.desc(),
                AuditEvent.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    )

    return AuditEventPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
