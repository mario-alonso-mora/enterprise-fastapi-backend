import secrets
import uuid
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


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "typ": "access",
    }
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


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthenticated()
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            # Tolerate up to five seconds of clock skew.
            leeway=timedelta(seconds=5),
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "aud", "iss"]},
        )
        if claims.get("typ") != "access":
            raise unauthenticated()
        user_id = uuid.UUID(claims["sub"])
    except (InvalidTokenError, ValueError, KeyError) as exc:
        raise unauthenticated() from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthenticated()
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user
