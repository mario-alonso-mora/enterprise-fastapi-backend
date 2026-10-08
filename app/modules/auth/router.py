from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, require_bootstrap_key
from app.db.session import get_db
from app.modules.auth.schemas import (
    LoginRequest,
    RegisterOrganization,
    RegistrationResult,
    TokenResponse,
)
from app.modules.auth.service import AlreadyExistsError, authenticate, register

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegistrationResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_bootstrap_key)],
)
def register_organization(payload: RegisterOrganization, db: Session = Depends(get_db)):
    try:
        user = register(payload, db)
    except AlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail="Organization slug or email already exists"
        ) from exc
    return RegistrationResult(
        organization_id=user.organization_id, user_id=user.id, email=user.email
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    user = authenticate(str(payload.email), payload.password, db)
    if user is None:
        raise HTTPException(
            status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"}
        )
    return TokenResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.access_token_minutes * 60,
    )
