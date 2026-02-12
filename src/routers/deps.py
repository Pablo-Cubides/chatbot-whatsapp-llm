"""
Shared dependencies for router modules.
These are used across multiple routers and were previously
defined inline in admin_panel.py.
"""

import logging

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

# Re-export auth dependencies from the auth service


def verify_token(authorization: str = Header(None)):
    """JWT-based token authentication (legacy dependency)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = authorization.replace("Bearer ", "")
    try:
        from src.services.auth_system import AuthManager

        auth = AuthManager()
        payload = auth.verify_token(token)
        return payload.get("sub", "admin")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")
