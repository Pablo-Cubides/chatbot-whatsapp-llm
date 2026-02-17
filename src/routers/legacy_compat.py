"""Legacy compatibility API routes kept for backward-compatible clients."""

from typing import Any

from fastapi import APIRouter, Depends

from src.services.auth_system import get_current_user

router = APIRouter(tags=["legacy-compat"])


@router.get("/api/verify")
def api_verify_legacy(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Compatibilidad con UI legacy para validar token."""
    return {"valid": True, "user": current_user}
