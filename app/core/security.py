import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.modules.auth.models import AuthSession
from app.modules.users.models import User

ph = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(
    user_id: uuid.UUID,
    settings: Settings,
    session_id: uuid.UUID | None = None,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "typ": "access",
    }
    if session_id is not None:
        payload["sid"] = str(session_id)

    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")


def require_bootstrap_key(
    x_bootstrap_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = settings.bootstrap_key.get_secret_value()
    if not x_bootstrap_key or not secrets.compare_digest(x_bootstrap_key, expected):
        raise HTTPException(status_code=401, detail="Invalid bootstrap key")


def unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@dataclass(frozen=True)
class AuthenticatedSession:
    user: User
    session_id: uuid.UUID


def get_authenticated_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedSession:
    """Validate the access JWT and its persistent database session."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthenticated()

    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            leeway=timedelta(seconds=5),
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "aud", "iss"]},
        )

        subject = claims.get("sub")
        sid = claims.get("sid")

        if (
            claims.get("typ") != "access"
            or not isinstance(subject, str)
            or not isinstance(sid, str)
        ):
            raise unauthenticated()

        user_id = uuid.UUID(subject)
        session_id = uuid.UUID(sid)

    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise unauthenticated() from exc

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise unauthenticated()

    session = db.get(AuthSession, session_id)

    if session is None or session.user_id != user.id or session.revoked_at is not None:
        raise unauthenticated()

    expires_at = session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at <= datetime.now(UTC):
        raise unauthenticated()

    return AuthenticatedSession(user=user, session_id=session_id)


def get_current_user(
    authentication: AuthenticatedSession = Depends(get_authenticated_session),
) -> User:
    return authentication.user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


def get_current_session_id(
    authentication: AuthenticatedSession = Depends(get_authenticated_session),
) -> uuid.UUID:
    """Return the verified, active session identifier."""
    return authentication.session_id
