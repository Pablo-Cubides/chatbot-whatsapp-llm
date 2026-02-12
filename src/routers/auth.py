"""
Authentication API Router
Extracted from admin_panel.py — handles login, logout, user info.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from src.routers.deps import (
    auth_manager,
    get_current_user,
    log_login,
    log_logout,
    security,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=dict[str, Any])
async def api_login(request: Request, credentials: dict[str, str]):
    """Login con JWT y auditoría"""
    username = credentials.get("username")
    password = credentials.get("password")

    if not username or not password:
        raise HTTPException(status_code=400, detail="Usuario y password requeridos")

    client_ip = request.client.host if request.client else None

    auth_result = auth_manager.authenticate_user(username, password)
    if not auth_result:
        log_login(
            username,
            "unknown",
            ip=client_ip,
            success=False,
            error="Credenciales inválidas",
        )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    access_token = auth_manager.create_access_token(auth_result)

    log_login(
        username,
        auth_result.get("role", "unknown"),
        ip=client_ip,
        success=True,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": auth_result,
        "expires_in": auth_manager.access_token_expire_minutes * 60,
    }


@router.post("/logout")
async def api_logout(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Logout con auditoría"""
    client_ip = request.client.host if request.client else None
    log_logout(
        current_user.get("username", "unknown"),
        current_user.get("role", "unknown"),
        ip=client_ip,
    )
    return {"message": "Logout exitoso"}


@router.get("/me", dependencies=[Depends(security)])
async def api_me(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Obtener info del usuario actual"""
    return current_user
