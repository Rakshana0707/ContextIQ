"""
auth.py

Administrative authentication and authorization dependency for ContextIQ Model Registry.
Protects sensitive lifecycle transitions, approvals, promotions, and rollbacks.
"""

import os
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)

DEFAULT_ADMIN_KEY = "contextiq-admin-secret"


def get_admin_key() -> str:
    """Returns the expected admin key from environment or default dev secret."""
    return os.getenv("CONTEXTIQ_ADMIN_KEY", DEFAULT_ADMIN_KEY)


def verify_admin_access(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """
    Validates administrative credentials.
    Accepts:
    1. 'X-Admin-Key' header matching CONTEXTIQ_ADMIN_KEY
    2. 'Authorization: Bearer <key>' matching CONTEXTIQ_ADMIN_KEY
    """
    expected_key = get_admin_key()

    # 1. Check header
    if x_admin_key and x_admin_key == expected_key:
        return "admin"

    # 2. Check Bearer token
    if credentials and credentials.credentials == expected_key:
        return "admin"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Administrative access required. Provide valid X-Admin-Key or Authorization Bearer header.",
        headers={"WWW-Authenticate": "Bearer"},
    )
