import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_admin
from app.db.session import get_db
from app.modules.customers.models import Customer
from app.modules.customers.repository import CustomerRepository
from app.modules.customers.schemas import (
    CustomerCreate,
    CustomerPage,
    CustomerRead,
    CustomerUpdate,
)
from app.modules.users.models import User

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("", response_model=CustomerRead, status_code=201)
def create_customer(
    payload: CustomerCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    customer = Customer(
        organization_id=admin.organization_id,
        external_ref=payload.external_ref,
        name=payload.name,
        email=str(payload.email) if payload.email is not None else None,
    )
    db.add(customer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Customer reference already exists") from exc
    db.refresh(customer)
    return customer


@router.get("", response_model=CustomerPage)
def list_customers(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customers, total = CustomerRepository(db, user.organization_id).page(offset, limit, q)
    return CustomerPage(items=customers, total=total, limit=limit, offset=offset)


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    customer = CustomerRepository(db, user.organization_id).get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    customer = CustomerRepository(db, admin.organization_id).get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is None:
        raise HTTPException(status_code=422, detail="Name cannot be null")
    for field, value in changes.items():
        setattr(customer, field, str(value) if value is not None else None)
    db.commit()
    db.refresh(customer)
    return customer
