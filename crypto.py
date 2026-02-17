"""
🔐 Sistema de Encriptación para Datos Sensibles
Implementación segura con Fernet para encriptar tokens OAuth, API keys, etc.
"""

import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Ruta por defecto para la clave Fernet
KEY_PATH = os.path.join(os.path.dirname(__file__), "data", "fernet.key")


def _harden_key_permissions(path: str) -> None:
    """Apply best-effort restrictive permissions to Fernet key file."""
    if os.name == "nt":
        current_user = os.environ.get("USERNAME")
        if not current_user:
            logger.warning("No se pudo determinar usuario actual para endurecer ACL de Fernet key")
            return

        commands = [
            ["icacls", path, "/inheritance:r"],
            ["icacls", path, "/grant:r", f"{current_user}:(R,W)"],
            ["icacls", path, "/remove:g", "Users", "Everyone", "Authenticated Users"],
        ]
        for command in commands:
            try:
                subprocess.run(command, check=False, capture_output=True, text=True)
            except Exception as e:
                logger.warning("No se pudo aplicar ACL segura a Fernet key: %s", e)
                break
        return

    try:
        import stat

        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, AttributeError) as e:
        logger.warning("No se pudo aplicar permisos restrictivos a Fernet key: %s", e)


def ensure_key() -> bytes:
    """
    Asegura que existe una clave Fernet.
    La genera si no existe.
    """
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    try:
        file_descriptor = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        _harden_key_permissions(KEY_PATH)
        with open(KEY_PATH, "rb") as f:
            return f.read()

    key = Fernet.generate_key()
    with os.fdopen(file_descriptor, "wb") as f:
        f.write(key)

    _harden_key_permissions(KEY_PATH)
    logger.info("Nueva clave Fernet generada y guardada")
    return key


def get_key_age_days() -> float:
    """Return Fernet key file age in days (0 if file does not exist)."""
    if not os.path.exists(KEY_PATH):
        return 0.0

    modified_at = datetime.fromtimestamp(os.path.getmtime(KEY_PATH), tz=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - modified_at).total_seconds() / 86400)


def is_key_rotation_due(rotation_days: int = 90) -> tuple[bool, float]:
    """Check whether Fernet key reached configured rotation age."""
    age_days = get_key_age_days()
    if rotation_days <= 0:
        return False, age_days
    return age_days >= rotation_days, age_days


def get_fernet() -> Fernet:
    """
    Obtiene instancia de Fernet usando clave de entorno o archivo.
    Prioriza FERNET_KEY de variables de entorno.
    """
    env_key = os.environ.get("FERNET_KEY")
    if env_key:
        key_bytes = env_key.encode("utf-8")
        return Fernet(key_bytes)
    return Fernet(ensure_key())


def encrypt_text(plaintext: str) -> str:
    """
    Encripta texto plano usando Fernet.

    Args:
        plaintext: Texto a encriptar

    Returns:
        Token encriptado como string
    """
    if not plaintext:
        return plaintext
    f = get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str) -> str:
    """
    Desencripta token Fernet a texto plano.

    Args:
        token: Token encriptado

    Returns:
        Texto desencriptado, o el valor original si falla
    """
    if not token:
        return token
    f = get_fernet()
    try:
        pt = f.decrypt(token.encode("utf-8"))
        return pt.decode("utf-8")
    except InvalidToken:
        logger.warning("Token inválido para desencriptar - posible dato no encriptado")
        return token
    except Exception as e:
        logger.error(f"Error desencriptando: {e}")
        return token


# =====================================
# Funciones específicas para OAuth Tokens
# =====================================


def encrypt_oauth_token(token: Optional[str]) -> Optional[str]:
    """
    Encripta un token OAuth para almacenamiento seguro en base de datos.

    Args:
        token: Token OAuth (access_token o refresh_token)

    Returns:
        Token encriptado o None si el input es None
    """
    if token is None:
        return None
    try:
        encrypted = encrypt_text(token)
        logger.debug("Token OAuth encriptado exitosamente")
        return encrypted
    except Exception as e:
        logger.error(f"Error encriptando token OAuth: {e}")
        raise ValueError("No se pudo encriptar el token OAuth") from e


def decrypt_oauth_token(encrypted_token: Optional[str]) -> Optional[str]:
    """
    Desencripta un token OAuth almacenado en base de datos.

    Args:
        encrypted_token: Token encriptado

    Returns:
        Token desencriptado o None si el input es None
    """
    if encrypted_token is None:
        return None
    try:
        decrypted = decrypt_text(encrypted_token)
        logger.debug("Token OAuth desencriptado exitosamente")
        return decrypted
    except Exception as e:
        logger.error(f"Error desencriptando token OAuth: {e}")
        return None


def encrypt_api_key(api_key: str) -> str:
    """
    Encripta una API key para almacenamiento seguro.

    Args:
        api_key: API key en texto plano

    Returns:
        API key encriptada
    """
    if not api_key:
        raise ValueError("API key no puede estar vacía")
    return encrypt_text(api_key)


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Desencripta una API key almacenada.

    Args:
        encrypted_key: API key encriptada

    Returns:
        API key en texto plano
    """
    if not encrypted_key:
        raise ValueError("API key encriptada no puede estar vacía")
    return decrypt_text(encrypted_key)


def is_encrypted(value: str) -> bool:
    """
    Verifica si un valor está encriptado con Fernet intentando desencriptarlo.

    Args:
        value: Valor a verificar

    Returns:
        True si está encriptado, False en caso contrario
    """
    if not value or len(value) < 10:
        return False
    try:
        f = get_fernet()
        f.decrypt(value.encode("utf-8"))
        return True
    except (InvalidToken, Exception):
        return False


def rotate_encryption_key(old_key: bytes, new_key: bytes, encrypted_value: str) -> str:
    """
    Rota la clave de encriptación para un valor encriptado.
    Útil para rotación periódica de claves de seguridad.

    Args:
        old_key: Clave Fernet anterior
        new_key: Nueva clave Fernet
        encrypted_value: Valor encriptado con la clave anterior

    Returns:
        Valor re-encriptado con la nueva clave
    """
    # Desencriptar con clave anterior
    try:
        old_fernet = Fernet(old_key)
        decrypted = old_fernet.decrypt(encrypted_value.encode()).decode()
    except InvalidToken:
        raise ValueError("No se pudo desencriptar con la clave anterior. Verifica que la clave sea correcta.")

    # Re-encriptar con nueva clave
    new_fernet = Fernet(new_key)
    new_encrypted = new_fernet.encrypt(decrypted.encode()).decode()

    logger.info("Valor re-encriptado con nueva clave exitosamente")
    return new_encrypted
