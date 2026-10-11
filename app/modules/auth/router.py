import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.rate_limit import limit_login, limit_refresh, limit_register
from app.core.security import (
    create_access_token,
    get_current_session_id,
    get_current_user,
    require_bootstrap_key,
)
from app.db.session import get_db
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    RegisterOrganization,
    RegistrationResult,
    SessionTokenResponse,
)
from app.modules.auth.service import AlreadyExistsError, authenticate, register
from app.modules.auth.session_service import (
    InvalidRefreshToken,
    create_session,
    revoke_session,
    rotate_refresh_token,
)
from app.modules.users.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegistrationResult,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_register), Depends(require_bootstrap_key)],
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


@router.post("/login", response_model=SessionTokenResponse, dependencies=[Depends(limit_login)])
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = authenticate(str(payload.email), payload.password, db)
    if user is None:
        raise HTTPException(
            status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"}
        )
    issued = create_session(user, db)

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return SessionTokenResponse(
        access_token=create_access_token(user.id, settings, session_id=issued.session_id),
        refresh_token=issued.refresh_token,
        session_expires_at=issued.expires_at,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post(
    "/refresh",
    response_model=SessionTokenResponse,
    dependencies=[Depends(limit_refresh)],
)
def refresh(
    payload: RefreshRequest,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    try:
        issued = rotate_refresh_token(payload.refresh_token, db)
    except InvalidRefreshToken as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        ) from exc

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return SessionTokenResponse(
        access_token=create_access_token(issued.user_id, settings, session_id=issued.session_id),
        refresh_token=issued.refresh_token,
        session_expires_at=issued.expires_at,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_user: User = Depends(get_current_user),
    session_id: uuid.UUID = Depends(get_current_session_id),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke only the session represented by the access JWT."""
    revoke_session(
        session_id=session_id,
        user_id=current_user.id,
        db=db,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
