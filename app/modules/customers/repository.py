import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.customers.models import Customer


class CustomerRepository:
    def __init__(self, db: Session, organization_id: uuid.UUID):
        self.db = db
        self.organization_id = organization_id

    def get(self, customer_id: uuid.UUID) -> Customer | None:
        return self.db.scalar(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.organization_id == self.organization_id,
            )
        )

    def page(self, offset: int, limit: int, q: str | None = None):
        predicate = [Customer.organization_id == self.organization_id]
        if q:
            predicate.append(Customer.name.ilike(f"%{q}%"))
        total = self.db.scalar(select(func.count()).select_from(Customer).where(*predicate)) or 0
        items = list(
            self.db.scalars(
                select(Customer)
                .where(*predicate)
                .order_by(Customer.created_at.desc(), Customer.id)
                .offset(offset)
                .limit(limit)
            )
        )
        return items, total
