from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.modules.auth.schemas import RegisterOrganization
from app.modules.organizations.models import Organization
from app.modules.users.models import User


class AlreadyExistsError(Exception):
    pass


def register(payload: RegisterOrganization, db: Session) -> User:
    email = str(payload.admin_email).lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AlreadyExistsError
    if (
        db.scalar(select(Organization.id).where(Organization.slug == payload.organization_slug))
        is not None
    ):
        raise AlreadyExistsError

    organization = Organization(name=payload.organization_name, slug=payload.organization_slug)
    try:
        db.add(organization)
        db.flush()  # May raise IntegrityError due to concurrent registration
        user = User(
            organization_id=organization.id,
            email=email,
            password_hash=hash_password(payload.admin_password),
            role="admin",
        )
        db.add(user)
        db.commit()  # Organization and admin are committed atomically
    except IntegrityError as exc:
        db.rollback()
        raise AlreadyExistsError from exc
    db.refresh(user)
    return user


def authenticate(email: str, password: str, db: Session) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user
