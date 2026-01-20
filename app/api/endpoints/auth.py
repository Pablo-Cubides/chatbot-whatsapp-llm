"""
🔐 Endpoints de Autenticación
Manejo de login, logout, tokens JWT y gestión de usuarios.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, status
from pydantic import BaseModel
from typing import Optional
import logging

from src.services.auth_system import (
    auth_manager, 
    get_current_user, 
    require_admin,
    LoginRequest,
    LoginResponse
)
from src.services.audit_system import log_login, log_logout

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UserInfoResponse(BaseModel):
    username: str
    role: str
    permissions: list


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, req: Request):
    """
    Inicia sesión y obtiene token JWT.
    
    - **username**: Nombre de usuario
    - **password**: Contraseña
    
    Returns JWT token para usar en endpoints protegidos.
    """
    user = auth_manager.authenticate_user(request.username, request.password)
    
    if not user:
        logger.warning(f"Login fallido para usuario: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Crear token
    token = auth_manager.create_access_token(user)
    
    # Registrar en auditoría
    client_ip = req.client.host if req.client else "unknown"
    await log_login(request.username, client_ip, success=True)
    
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=auth_manager.access_token_expire_minutes * 60,
        user_info=user
    )


@router.post("/logout")
async def logout(
    req: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Cierra sesión del usuario actual.
    
    En JWT stateless, no hay invalidación real del token,
    pero registramos el evento para auditoría.
    """
    username = current_user.get("username", "unknown")
    client_ip = req.client.host if req.client else "unknown"
    
    await log_logout(username, client_ip)
    
    return {
        "status": "success",
        "message": "Sesión cerrada correctamente",
        "note": "El token sigue siendo válido hasta su expiración"
    }


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Obtiene información del usuario actual autenticado.
    """
    return UserInfoResponse(
        username=current_user.get("username", current_user.get("sub", "unknown")),
        role=current_user.get("role", "unknown"),
        permissions=current_user.get("permissions", [])
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Cambia la contraseña del usuario actual.
    
    - **current_password**: Contraseña actual
    - **new_password**: Nueva contraseña (mínimo 8 caracteres)
    """
    username = current_user.get("username", current_user.get("sub"))
    
    if not username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo determinar el usuario"
        )
    
    success = auth_manager.change_password(
        username,
        request.current_password,
        request.new_password
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo cambiar la contraseña. Verifica que la contraseña actual sea correcta y la nueva tenga al menos 8 caracteres."
        )
    
    return {
        "status": "success",
        "message": "Contraseña actualizada correctamente"
    }


@router.get("/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """
    Verifica si el token actual es válido.
    
    Útil para verificar estado de autenticación en frontend.
    """
    return {
        "valid": True,
        "username": current_user.get("username", current_user.get("sub")),
        "role": current_user.get("role"),
        "legacy_auth": current_user.get("legacy_auth", False)
    }
