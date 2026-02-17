"""
Shared dependencies for router modules.
These are used across multiple routers and were previously
defined inline in admin_panel.py.
"""

import logging

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

# Re-export commonly-used services/dependencies
from src.services.alert_system import alert_manager  # noqa: F401
from src.services.audit_system import audit_manager, log_bulk_send, log_login, log_logout, log_security_event  # noqa: F401
from src.services.auth_system import auth_manager, get_current_user, require_admin  # noqa: F401
from src.services.queue_system import queue_manager  # noqa: F401
from src.services.whatsapp_cloud_provider import verify_webhook  # noqa: F401
from src.services.whatsapp_provider import get_provider  # noqa: F401

__all__ = [
    "alert_manager",
    "audit_manager",
    "auth_manager",
    "get_current_user",
    "get_provider",
    "log_bulk_send",
    "log_login",
    "log_logout",
    "log_security_event",
    "queue_manager",
    "require_admin",
    "verify_token",
    "verify_webhook",
]


def verify_token(authorization: str = Header(None)) -> str:
    """JWT-based token authentication (legacy dependency)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication token")

    token = authorization.replace("Bearer ", "")
    payload = auth_manager.verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")
    subject = payload.get("sub")
    if not subject or not isinstance(subject, str):
        raise HTTPException(status_code=401, detail="Invalid authentication token payload")
    return subject
