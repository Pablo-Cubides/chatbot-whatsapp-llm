import os
from cryptography.fernet import Fernet

KEY_PATH = os.path.join(os.path.dirname(__file__), "data", "fernet.key")


def ensure_key() -> bytes:
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    if os.path.exists(KEY_PATH):
        return open(KEY_PATH, "rb").read()
    key = Fernet.generate_key()
    open(KEY_PATH, "wb").write(key)
    return key


def get_fernet() -> Fernet:
    key = os.environ.get("FERNET_KEY")
    if key:
        if isinstance(key, str):
            key = key.encode()
        return Fernet(key)
    k = ensure_key()
    return Fernet(k)


def encrypt_text(plaintext: str) -> str:
    f = get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(token: str) -> str:
    f = get_fernet()
    try:
        pt = f.decrypt(token.encode("utf-8"))
        return pt.decode("utf-8")
    except Exception:
        # If decryption fails, return original
        return token
