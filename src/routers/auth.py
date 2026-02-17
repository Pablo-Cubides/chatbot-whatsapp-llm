"""
Authentication API Router
Extracted from admin_panel.py — handles login, logout, user info.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.models.validation_models import AuthLoginModel
from src.services.protection_system import get_client_ip, rate_limit

from src.routers.deps import (
    auth_manager,
    get_current_user,
    log_login,
    log_logout,
    log_security_event,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LogoutResponse(BaseModel):
    message: str


class MeResponse(BaseModel):
    sub: str
    username: str
    role: str
    permissions: list[str] = Field(default_factory=list)


def _login_rate_limit_identifier(*args, **kwargs) -> str:
    """Rate limit key for auth attempts (IP + username)."""
    request = kwargs.get("request")
    credentials = kwargs.get("credentials")

    if request is None:
        request = next((arg for arg in args if isinstance(arg, Request)), None)
    if credentials is None:
        credentials = next((arg for arg in args if isinstance(arg, AuthLoginModel)), None)

    username = credentials.username if isinstance(credentials, AuthLoginModel) else "unknown"
    client_ip = get_client_ip(request) if request is not None else "unknown"
    return f"auth:{client_ip}:{username}"


@router.post("/login", response_model=dict[str, Any])
@rate_limit("auth_attempts", identifier_func=_login_rate_limit_identifier)
async def api_login(request: Request, response: Response, credentials: AuthLoginModel) -> dict[str, Any]:
    """Login con JWT y auditoría"""
    username = credentials.username
    password = credentials.password

    if not username or not password:
        raise HTTPException(status_code=400, detail="Usuario y password requeridos")

    client_ip = request.client.host if request.client else None

    auth_result, error_code, lockout_seconds = auth_manager.authenticate_user_detailed(username, password)
    if error_code == "account_locked":
        log_security_event(
            "login_lockout",
            username=username,
            role="unknown",
            ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            success=False,
            details={"reason": "account_locked", "lockout_seconds": lockout_seconds or 0},
            error="Account temporarily locked",
        )
        raise HTTPException(
            status_code=423,
            detail=f"Cuenta bloqueada temporalmente por múltiples intentos fallidos. Reintenta en {lockout_seconds or 0} segundos.",
        )

    if auth_result is None:
        log_security_event(
            "login_failed",
            username=username,
            role="unknown",
            ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            success=False,
            details={"reason": "invalid_credentials"},
            error="Invalid credentials",
        )
        log_login(
            username,
            "unknown",
            ip=client_ip,
            success=False,
            error="Credenciales inválidas",
        )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    token_pair = auth_manager.create_token_pair(auth_result)
    access_token = token_pair["access_token"]
    refresh_token = token_pair["refresh_token"]

    response.set_cookie(
        key=auth_manager.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=auth_manager.refresh_cookie_secure,
        samesite=auth_manager.refresh_cookie_samesite,
        max_age=auth_manager.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )

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


@router.post("/logout", response_model=LogoutResponse)
async def api_logout(
    request: Request,
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> LogoutResponse:
    """Logout con auditoría"""
    client_ip = request.client.host if request.client else None
    auth_manager.revoke_token_payload(current_user, revoke_session=True)

    refresh_token = request.cookies.get(auth_manager.refresh_cookie_name)
    if refresh_token:
        payload = auth_manager.verify_token(refresh_token, expected_type="refresh")
        if payload is not None:
            auth_manager.revoke_token_payload(payload, revoke_session=False)

    response.delete_cookie(key=auth_manager.refresh_cookie_name, path="/")

    log_logout(
        current_user.get("username", "unknown"),
        current_user.get("role", "unknown"),
        ip=client_ip,
    )
    return LogoutResponse(message="Logout exitoso")


@router.post("/refresh", response_model=dict[str, Any])
async def api_refresh(request: Request, response: Response) -> dict[str, Any]:
    """Renovar access token a partir de refresh token en cookie HttpOnly."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    refresh_token = request.cookies.get(auth_manager.refresh_cookie_name)
    if not refresh_token:
        log_security_event(
            "refresh_failed",
            ip=client_ip,
            user_agent=user_agent,
            success=False,
            details={"reason": "missing_refresh_cookie"},
            error="Refresh token missing",
        )
        raise HTTPException(status_code=401, detail="Refresh token requerido")

    refresh_payload = auth_manager.verify_token(refresh_token, expected_type="refresh")
    if refresh_payload is None:
        log_security_event(
            "refresh_failed",
            ip=client_ip,
            user_agent=user_agent,
            success=False,
            details={"reason": "invalid_refresh_token"},
            error="Refresh token invalid or expired",
        )
        raise HTTPException(status_code=401, detail="Refresh token inválido o expirado")

    # Rotation: invalidar refresh token usado para evitar replay.
    auth_manager.revoke_token_payload(refresh_payload, revoke_session=False)

    user_info = {
        "username": refresh_payload.get("sub"),
        "role": refresh_payload.get("role", "operator"),
        "permissions": refresh_payload.get("permissions", []),
        "auth_time": refresh_payload.get("auth_time"),
    }
    session_id = refresh_payload.get("sid")

    access_token = auth_manager.create_access_token(user_info, session_id=session_id)
    new_refresh_token = auth_manager.create_refresh_token(user_info, session_id=session_id)

    response.set_cookie(
        key=auth_manager.refresh_cookie_name,
        value=new_refresh_token,
        httponly=True,
        secure=auth_manager.refresh_cookie_secure,
        samesite=auth_manager.refresh_cookie_samesite,
        max_age=auth_manager.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_info": user_info,
        "expires_in": auth_manager.access_token_expire_minutes * 60,
    }


@router.get("/me", response_model=MeResponse)
async def api_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> MeResponse:
    """Obtener info del usuario actual"""
    return MeResponse(
        sub=str(current_user.get("sub") or current_user.get("username") or "unknown"),
        username=str(current_user.get("sub") or current_user.get("username") or "unknown"),
        role=str(current_user.get("role") or "unknown"),
        permissions=[str(p) for p in (current_user.get("permissions") or [])],
    )


@router.post("/ws-token", response_model=dict[str, Any])
async def api_ws_token(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Emitir token WebSocket de vida corta para canal de métricas."""
    user_info = {
        "username": current_user.get("sub") or current_user.get("username"),
        "role": current_user.get("role", "operator"),
        "permissions": current_user.get("permissions", []),
    }
    ws_token = auth_manager.create_ws_token(
        user_info,
        scope="metrics",
        session_id=current_user.get("sid"),
    )
    log_security_event(
        "ws_token_issued",
        username=user_info.get("username") or "unknown",
        role=user_info.get("role", "unknown"),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        success=True,
        details={"scope": "metrics"},
    )

    return {
        "ws_token": ws_token,
        "token_type": "bearer",
        "scope": "metrics",
        "expires_in": auth_manager.ws_token_expire_minutes * 60,
    }
