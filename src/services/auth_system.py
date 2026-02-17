"""
🔐 Sistema de Autenticación Seguro para Admin Panel
Implementación robusta con bcrypt y configuración desde variables de entorno
"""

import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    user_info: dict


class AuthManager:
    def __init__(self):
        # JWT Configuration
        self.secret_key = self._get_jwt_secret()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours default
        self.refresh_token_expire_days = int(os.environ.get("JWT_REFRESH_EXPIRE_DAYS", "7"))
        self.ws_token_expire_minutes = int(os.environ.get("JWT_WS_EXPIRE_MINUTES", "2"))
        self.max_session_hours = int(os.environ.get("JWT_MAX_SESSION_HOURS", "24"))

        # Security controls
        self.max_failed_login_attempts = int(os.environ.get("AUTH_MAX_FAILED_LOGIN_ATTEMPTS", "5"))
        self.account_lockout_minutes = int(os.environ.get("AUTH_LOCKOUT_MINUTES", "15"))

        # Frontend cookie config
        self.refresh_cookie_name = os.environ.get("JWT_REFRESH_COOKIE_NAME", "refresh_token")
        self.refresh_cookie_secure = os.environ.get("JWT_REFRESH_COOKIE_SECURE", "false").lower() == "true"
        self.refresh_cookie_samesite = os.environ.get("JWT_REFRESH_COOKIE_SAMESITE", "lax")

        # User Configuration
        self.users = self._initialize_users()

        # Runtime security state (in-memory fallback)
        self._failed_login_attempts: dict[str, list[float]] = {}
        self._account_lockout_until: dict[str, float] = {}
        self._revoked_token_jtis: dict[str, int] = {}
        self._revoked_session_ids: dict[str, int] = {}
        self._user_last_logout_ts: dict[str, int] = {}

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
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verificar password contra hash bcrypt"""
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error verificando password: {e}")
            return False

    def _initialize_users(self) -> dict[str, dict[str, Any]]:
        """Inicializar usuarios desde variables de entorno"""
        users = {}

        # Usuario administrador
        admin_username = os.environ.get("ADMIN_USERNAME", "admin")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if not admin_password:
            raise ValueError(
                "ADMIN_PASSWORD no está configurado en variables de entorno. "
                "Por favor configura una contraseña segura de al menos 8 caracteres."
            )

        users[admin_username] = {
            "password_hash": self._hash_password(admin_password),
            "role": "admin",
            "permissions": ["all"],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Usuario operador
        operator_username = os.environ.get("OPERATOR_USERNAME", "operator")
        operator_password = os.environ.get("OPERATOR_PASSWORD")

        if operator_password:
            users[operator_username] = {
                "password_hash": self._hash_password(operator_password),
                "role": "operator",
                "permissions": ["view", "config"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(f"Inicializados {len(users)} usuarios del sistema")
        return users

    def authenticate_user(self, username: str, password: str) -> Optional[dict[str, Any]]:
        """Autenticar usuario con validación segura"""
        auth_result, _, _ = self.authenticate_user_detailed(username, password)
        return auth_result

    def authenticate_user_detailed(self, username: str, password: str) -> tuple[Optional[dict[str, Any]], Optional[str], Optional[int]]:
        """Autenticación con detalle de errores para lockout y auditoría."""
        self._cleanup_security_state()

        is_locked, lockout_seconds = self._is_account_locked(username)
        if is_locked:
            logger.warning(f"Cuenta temporalmente bloqueada para usuario: {username}")
            return None, "account_locked", lockout_seconds

        user = self.users.get(username)
        if not user:
            logger.warning(f"Intento de login con usuario inexistente: {username}")
            return None, "invalid_credentials", None

        if not self._verify_password(password, user["password_hash"]):
            logger.warning(f"Password incorrecto para usuario: {username}")
            locked, seconds = self._register_failed_login(username)
            if locked:
                return None, "account_locked", seconds
            return None, "invalid_credentials", None

        self._reset_failed_login(username)

        logger.info(f"Login exitoso para usuario: {username}")
        return {
            "username": username,
            "role": user["role"],
            "permissions": user["permissions"],
            "login_time": datetime.now(timezone.utc).isoformat(),
        }, None, None

    def _create_token(self, user_data: dict[str, Any], token_type: str, expires_delta: timedelta, session_id: str | None = None) -> str:
        """Crear JWT token con claims de seguridad."""
        to_encode = user_data.copy()
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        auth_time = to_encode.get("auth_time")
        if not isinstance(auth_time, (int, float)):
            auth_time = int(now.timestamp())
        sid = session_id or uuid.uuid4().hex
        to_encode.update(
            {
                "exp": expire,
                "iat": now,
                "auth_time": int(auth_time),
                "iss": "whatsapp-chatbot-api",
                "sub": user_data["username"],
                "jti": uuid.uuid4().hex,
                "type": token_type,
                "sid": sid,
            }
        )

        try:
            token = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            logger.info(f"Token JWT ({token_type}) creado para usuario: {user_data['username']}")
            return token
        except Exception as e:
            logger.error(f"Error creando JWT token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno generando token de acceso"
            )

    def create_access_token(self, user_data: dict[str, Any], session_id: str | None = None) -> str:
        """Crear JWT access token seguro."""
        return self._create_token(
            user_data=user_data,
            token_type="access",
            expires_delta=timedelta(minutes=self.access_token_expire_minutes),
            session_id=session_id,
        )

    def create_refresh_token(self, user_data: dict[str, Any], session_id: str | None = None) -> str:
        """Crear JWT refresh token seguro."""
        return self._create_token(
            user_data=user_data,
            token_type="refresh",
            expires_delta=timedelta(days=self.refresh_token_expire_days),
            session_id=session_id,
        )

    def create_token_pair(self, user_data: dict[str, Any]) -> dict[str, str]:
        """Crear par access+refresh con la misma sesión."""
        session_id = uuid.uuid4().hex
        return {
            "access_token": self.create_access_token(user_data, session_id=session_id),
            "refresh_token": self.create_refresh_token(user_data, session_id=session_id),
        }

    def create_ws_token(self, user_data: dict[str, Any], scope: str, session_id: str | None = None) -> str:
        """Crear token corto y con scope para canales WebSocket."""
        ws_payload = user_data.copy()
        ws_payload["ws_scope"] = scope
        return self._create_token(
            user_data=ws_payload,
            token_type="ws",
            expires_delta=timedelta(minutes=self.ws_token_expire_minutes),
            session_id=session_id,
        )

    def verify_token(self, token: str, expected_type: str | None = None) -> Optional[dict[str, Any]]:
        """Verificar y decodificar JWT token"""
        try:
            self._cleanup_security_state()
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm], options={"verify_exp": True, "verify_iat": True}
            )

            username = payload.get("sub")
            if username is None:
                logger.warning("Token JWT sin subject (username)")
                return None

            if expected_type and payload.get("type") != expected_type:
                logger.warning("Token JWT con tipo inválido. Esperado=%s, recibido=%s", expected_type, payload.get("type"))
                return None

            # Verificar que el usuario aún existe
            if username not in self.users:
                logger.warning(f"Token para usuario inexistente: {username}")
                return None

            jti = payload.get("jti")
            if jti and jti in self._revoked_token_jtis:
                logger.info("Token JWT revocado (jti=%s)", jti)
                return None

            sid = payload.get("sid")
            if sid and sid in self._revoked_session_ids:
                logger.info("Sesión JWT revocada (sid=%s)", sid)
                return None

            iat_claim = payload.get("iat")
            iat_ts = int(iat_claim.timestamp()) if isinstance(iat_claim, datetime) else int(iat_claim or 0)
            if username in self._user_last_logout_ts and iat_ts < self._user_last_logout_ts[username]:
                logger.info("Token JWT emitido antes de último logout de usuario=%s", username)
                return None

            auth_time = payload.get("auth_time")
            auth_ts = int(auth_time) if isinstance(auth_time, (int, float)) else iat_ts
            max_session_seconds = self.max_session_hours * 60 * 60
            if auth_ts > 0 and (int(time.time()) - auth_ts) > max_session_seconds:
                logger.info("Sesión JWT excedió vida máxima para usuario=%s", username)
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
        if not any(c.isupper() for c in new_password) or not any(c.isdigit() for c in new_password):
            logger.warning(f"Nueva password no cumple requisitos de complejidad para usuario: {username}")
            return False

        # Actualizar password
        self.users[username]["password_hash"] = self._hash_password(new_password)
        self.users[username]["password_changed_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Password cambiado exitosamente para usuario: {username}")
        return True

    def revoke_token_payload(self, payload: dict[str, Any], revoke_session: bool = True) -> None:
        """Revocar token y opcionalmente su sesión asociada."""
        self._cleanup_security_state()
        expiry_ts = self._extract_expiry_timestamp(payload)

        jti = payload.get("jti")
        if isinstance(jti, str) and jti:
            self._revoked_token_jtis[jti] = expiry_ts

        username = payload.get("sub")
        if isinstance(username, str) and username:
            self._user_last_logout_ts[username] = int(time.time())

        if revoke_session:
            sid = payload.get("sid")
            if isinstance(sid, str) and sid:
                session_exp = int(time.time()) + (self.refresh_token_expire_days * 24 * 60 * 60)
                self._revoked_session_ids[sid] = session_exp

    def reset_runtime_state(self) -> None:
        """Reset de estado dinámico para tests/entornos efímeros."""
        self._failed_login_attempts.clear()
        self._account_lockout_until.clear()
        self._revoked_token_jtis.clear()
        self._revoked_session_ids.clear()
        self._user_last_logout_ts.clear()

    def _cleanup_security_state(self) -> None:
        now = int(time.time())
        self._revoked_token_jtis = {jti: exp for jti, exp in self._revoked_token_jtis.items() if exp > now}
        self._revoked_session_ids = {sid: exp for sid, exp in self._revoked_session_ids.items() if exp > now}
        self._account_lockout_until = {
            username: lock_until for username, lock_until in self._account_lockout_until.items() if lock_until > now
        }

        window_seconds = 5 * 60
        cutoff = time.time() - window_seconds
        for username, attempts in list(self._failed_login_attempts.items()):
            filtered = [attempt for attempt in attempts if attempt >= cutoff]
            if filtered:
                self._failed_login_attempts[username] = filtered
            else:
                self._failed_login_attempts.pop(username, None)

    def _is_account_locked(self, username: str) -> tuple[bool, Optional[int]]:
        lock_until = self._account_lockout_until.get(username)
        if lock_until is None:
            return False, None

        now = time.time()
        if lock_until <= now:
            self._account_lockout_until.pop(username, None)
            self._failed_login_attempts.pop(username, None)
            return False, None

        return True, int(lock_until - now)

    def _register_failed_login(self, username: str) -> tuple[bool, Optional[int]]:
        attempts = self._failed_login_attempts.get(username, [])
        now = time.time()
        window_start = now - (5 * 60)
        attempts = [attempt for attempt in attempts if attempt >= window_start]
        attempts.append(now)
        self._failed_login_attempts[username] = attempts

        if len(attempts) >= self.max_failed_login_attempts:
            lock_until = now + (self.account_lockout_minutes * 60)
            self._account_lockout_until[username] = lock_until
            return True, int(self.account_lockout_minutes * 60)

        return False, None

    def _reset_failed_login(self, username: str) -> None:
        self._failed_login_attempts.pop(username, None)
        self._account_lockout_until.pop(username, None)

    @staticmethod
    def _extract_expiry_timestamp(payload: dict[str, Any]) -> int:
        exp_claim = payload.get("exp")
        if isinstance(exp_claim, datetime):
            return int(exp_claim.timestamp())
        if isinstance(exp_claim, (int, float)):
            return int(exp_claim)
        return int(time.time()) + 3600


# Instancia global
auth_manager = AuthManager()
security = HTTPBearer(auto_error=False)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency para obtener usuario actual autenticado (JWT)."""
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

    # Token inválido
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency para endpoints que requieren rol admin"""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: se requiere rol de administrador")
    return current_user


async def require_operator_or_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency para endpoints que requieren rol operator o admin"""
    allowed_roles = ["admin", "operator"]
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado: se requiere rol de operador o administrador"
        )
    return current_user
