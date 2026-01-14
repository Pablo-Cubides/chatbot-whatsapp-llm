"""
🔐 Sistema de Autenticación Seguro para Admin Panel
Implementación robusta con bcrypt y configuración desde variables de entorno
"""

import jwt
import bcrypt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: dict

class AuthManager:
    def __init__(self):
        # JWT Configuration
        self.secret_key = self._get_jwt_secret()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours default
        
        # User Configuration
        self.users = self._initialize_users()

    def _get_jwt_secret(self) -> str:
        """Obtener secret JWT desde variables de entorno con validación"""
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            raise ValueError(
                "JWT_SECRET no está configurado en variables de entorno. "
                "Por favor configura una clave segura de al menos 32 caracteres."
            )
        if len(secret) < 32:
            logger.warning("JWT_SECRET es muy corto. Se recomienda al menos 32 caracteres para seguridad óptima.")
        return secret
    
    def _hash_password(self, password: str) -> str:
        """Hash seguro de password usando bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verificar password contra hash bcrypt"""
        try:
            return bcrypt.checkpw(
                plain_password.encode('utf-8'), 
                hashed_password.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"Error verificando password: {e}")
            return False
    
    def _initialize_users(self) -> Dict[str, Dict[str, Any]]:
        """Inicializar usuarios desde variables de entorno"""
        users = {}
        
        # Usuario administrador
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD")
        
        if not admin_password:
            logger.warning(
                "ADMIN_PASSWORD no configurado. Usando password por defecto. "
                "¡CAMBIAR INMEDIATAMENTE EN PRODUCCIÓN!"
            )
            admin_password = "admin123"
            
        users[admin_username] = {
            "password_hash": self._hash_password(admin_password),
            "role": "admin",
            "permissions": ["all"],
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Usuario operador
        operator_username = os.environ.get("OPERATOR_USERNAME", "operator")
        operator_password = os.environ.get("OPERATOR_PASSWORD")
        
        if operator_password:
            users[operator_username] = {
                "password_hash": self._hash_password(operator_password),
                "role": "operator",
                "permissions": ["view", "config"],
                "created_at": datetime.utcnow().isoformat()
            }
        
        logger.info(f"Inicializados {len(users)} usuarios del sistema")
        return users
        
    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Autenticar usuario con validación segura"""
        user = self.users.get(username)
        if not user:
            logger.warning(f"Intento de login con usuario inexistente: {username}")
            return None
            
        if not self._verify_password(password, user["password_hash"]):
            logger.warning(f"Password incorrecto para usuario: {username}")
            return None
            
        logger.info(f"Login exitoso para usuario: {username}")
        return {
            "username": username,
            "role": user["role"],
            "permissions": user["permissions"],
            "login_time": datetime.utcnow().isoformat()
        }
    
    def create_access_token(self, user_data: Dict[str, Any]) -> str:
        """Crear JWT token seguro"""
        to_encode = user_data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": "whatsapp-chatbot-api",
            "sub": user_data["username"]
        })
        
        try:
            token = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            logger.info(f"Token JWT creado para usuario: {user_data['username']}")
            return token
        except Exception as e:
            logger.error(f"Error creando JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno generando token de acceso"
            )
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verificar y decodificar JWT token"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                options={"verify_exp": True, "verify_iat": True}
            )
            
            username = payload.get("sub")
            if username is None:
                logger.warning("Token JWT sin subject (username)")
                return None
                
            # Verificar que el usuario aún existe
            if username not in self.users:
                logger.warning(f"Token para usuario inexistente: {username}")
                return None
                
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.info("Token JWT expirado")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Token JWT inválido: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verificando token: {e}")
            return None
    
    def change_password(self, username: str, current_password: str, new_password: str) -> bool:
        """Cambiar password de usuario"""
        user = self.users.get(username)
        if not user:
            return False
            
        if not self._verify_password(current_password, user["password_hash"]):
            logger.warning(f"Intento de cambio de password con password actual incorrecto: {username}")
            return False
            
        # Validar nueva password
        if len(new_password) < 8:
            logger.warning(f"Nueva password muy corta para usuario: {username}")
            return False
            
        # Actualizar password
        self.users[username]["password_hash"] = self._hash_password(new_password)
        self.users[username]["password_changed_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Password cambiado exitosamente para usuario: {username}")
        return True

# Instancia global
auth_manager = AuthManager()
security = HTTPBearer(auto_error=False)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency para obtener usuario actual autenticado (JWT o legacy token)"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autorización requerido",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Intentar verificar como JWT primero
    user = auth_manager.verify_token(token)
    if user is not None:
        return user
    
    # Fallback a legacy token si está habilitado
    legacy_enabled = os.environ.get("LEGACY_TOKEN_ENABLED", "false").lower() == "true"
    legacy_token = os.environ.get("LEGACY_ADMIN_TOKEN", "admintoken")
    
    if legacy_enabled and token == legacy_token:
        logger.warning("⚠️ Uso de legacy token detectado. Migrar a JWT lo antes posible.")
        return {
            "sub": "admin",
            "username": "admin",
            "role": "admin",
            "permissions": ["all"],
            "legacy_auth": True
        }
    
    # Token inválido
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency para endpoints que requieren rol admin"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requiere rol de administrador"
        )
    return current_user

async def require_operator_or_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency para endpoints que requieren rol operator o admin"""
    allowed_roles = ["admin", "operator"]
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: se requiere rol de operador o administrador"
        )
    return current_user

# Modelos Pydantic para autenticación
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_info: Dict[str, Any]
    expires_in: int
