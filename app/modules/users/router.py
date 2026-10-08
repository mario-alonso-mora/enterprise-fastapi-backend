from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_current_user, hash_password, require_admin
from app.db.session import get_db
from app.modules.users.models import User
from app.modules.users.schemas import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("", response_model=list[UserRead])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(User).where(User.organization_id == admin.organization_id).order_by(User.email)
        )
    )


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    user = User(
        organization_id=admin.organization_id,
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists") from exc
    db.refresh(user)
    return user
