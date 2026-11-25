"""
Authentication and Authorization dependencies (ContextIQ Phase 7.9).
Provides:
- JWT verification and subject extraction
- Token revocation and blacklist check
- User-level data isolation
- Role-based administrative access enforcement (require_admin)
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Dict, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


class TokenBlacklist:
    """Thread-safe in-memory store for revoked JWT tokens."""

    _revoked: Dict[str, float] = {}  # token -> expiry_timestamp
    _lock = threading.Lock()

    @classmethod
    def revoke(cls, token: str, expiry_timestamp: Optional[float] = None) -> None:
        with cls._lock:
            # Default retention in blacklist: 24h
            exp = expiry_timestamp or (time.time() + 86400)
            cls._revoked[token] = exp
            cls._prune_expired()

    @classmethod
    def is_revoked(cls, token: str) -> bool:
        with cls._lock:
            if token in cls._revoked:
                if time.time() > cls._revoked[token]:
                    del cls._revoked[token]
                    return False
                return True
            return False

    @classmethod
    def _prune_expired(cls) -> None:
        now = time.time()
        to_delete = [t for t, exp in cls._revoked.items() if exp < now]
        for t in to_delete:
            del cls._revoked[t]

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._revoked.clear()


def get_current_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    """Resolve identity from a verified JWT; permit X-User-Id only in development."""
    settings = get_settings()

    if credentials is not None:
        # Check token blacklist (revoked session)
        if TokenBlacklist.is_revoked(credentials.credentials):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again.",
            )

        try:
            claims = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
            subject = claims.get("sub")
            if not subject:
                raise ValueError("missing subject")
            return uuid.UUID(subject)
        except (JWTError, ValueError) as exc:
            logger.info("Rejected invalid bearer token: %s", type(exc).__name__)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
            ) from exc

    if settings.APP_ENV != "development":
        if x_user_id is not None:
            logger.warning("Rejected X-User-Id header in APP_ENV=%s (development-only fallback)", settings.APP_ENV)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials.")


def get_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the full current User row, raising 401 if user does not exist."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive.")
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Enforces that the current authenticated user has administrative privileges."""
    is_admin_user = getattr(current_user, "is_admin", False) or current_user.role_persona == "admin"
    if not is_admin_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )
    return current_user
