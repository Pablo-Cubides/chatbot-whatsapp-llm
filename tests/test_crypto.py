"""
Tests for the Crypto module — Fernet encryption/decryption.
"""

import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

pytestmark = pytest.mark.unit


class TestCrypto:
    """Test suite for crypto.py encryption functions."""

    def setup_method(self):
        """Fresh import for each test to avoid state leakage."""
        # Generate a deterministic test key
        self.test_key = Fernet.generate_key()
        self.fernet = Fernet(self.test_key)

    # ── ensure_key_exists ──

    def test_ensure_key_creates_file(self, tmp_path):
        """Should create a key file if none exists."""
        from unittest.mock import patch as mock_patch

        from crypto import ensure_key

        key_path = str(tmp_path / "test.key")
        with mock_patch("crypto.KEY_PATH", key_path):
            key = ensure_key()
        assert os.path.exists(key_path)
        assert isinstance(key, bytes)
        # Valid Fernet key is base64-encoded, 44 chars
        assert len(key) == 44

    def test_ensure_key_idempotent(self, tmp_path):
        """Should not overwrite an existing key file."""
        from unittest.mock import patch as mock_patch

        from crypto import ensure_key

        key_path = str(tmp_path / "test.key")
        with mock_patch("crypto.KEY_PATH", key_path):
            first_key = ensure_key()
            second_key = ensure_key()

        assert first_key == second_key

    # ── encrypt_text / decrypt_text ──

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt should return original text."""
        from crypto import decrypt_text, encrypt_text

        with patch("crypto.get_fernet") as mock_fernet:
            mock_fernet.return_value = self.fernet
            plaintext = "hello-world-secret"
            encrypted = encrypt_text(plaintext)
            assert encrypted != plaintext
            decrypted = decrypt_text(encrypted)
            assert decrypted == plaintext

    def test_decrypt_invalid_token_returns_none(self):
        """Decrypting garbage should return original value and not crash."""
        from crypto import decrypt_text

        with patch("crypto.get_fernet") as mock_fernet:
            mock_fernet.return_value = self.fernet
            invalid = "not-a-valid-fernet-token"
            result = decrypt_text(invalid)
            assert result == invalid

    def test_encrypt_empty_string(self):
        """Encrypting an empty string should still work."""
        from crypto import decrypt_text, encrypt_text

        with patch("crypto.get_fernet") as mock_fernet:
            mock_fernet.return_value = self.fernet
            encrypted = encrypt_text("")
            decrypted = decrypt_text(encrypted)
            assert decrypted == ""

    # ── is_encrypted ──

    def test_is_encrypted_true_for_fernet_token(self):
        """Should detect a valid Fernet token."""
        from crypto import is_encrypted

        token = self.fernet.encrypt(b"test").decode()
        with patch("crypto.get_fernet", return_value=self.fernet):
            assert is_encrypted(token) is True

    def test_is_encrypted_false_for_plaintext(self):
        """Should return False for non-encrypted strings."""
        from crypto import is_encrypted

        assert is_encrypted("just-plain-text") is False
        assert is_encrypted("") is False
        assert is_encrypted("short") is False

    # ── encrypt_oauth_token / decrypt_oauth_token ──

    def test_oauth_token_roundtrip(self):
        """OAuth token encrypt/decrypt should be reversible."""
        from crypto import decrypt_oauth_token, encrypt_oauth_token

        with patch("crypto.get_fernet") as mock_fernet:
            mock_fernet.return_value = self.fernet
            token = "ya29.abcdef1234567890"
            encrypted = encrypt_oauth_token(token)
            decrypted = decrypt_oauth_token(encrypted)
            assert decrypted == token

    # ── encrypt_api_key / decrypt_api_key ──

    def test_api_key_roundtrip(self):
        """API key encrypt/decrypt should be reversible."""
        from crypto import decrypt_api_key, encrypt_api_key

        with patch("crypto.get_fernet") as mock_fernet:
            mock_fernet.return_value = self.fernet
            key = "sk-1234567890abcdef"
            encrypted = encrypt_api_key(key)
            decrypted = decrypt_api_key(encrypted)
            assert decrypted == key

    def test_encrypt_api_key_empty_raises(self):
        """Encrypting an empty API key should raise ValueError."""
        from crypto import encrypt_api_key

        with pytest.raises(ValueError):
            encrypt_api_key("")

    def test_decrypt_api_key_empty_raises(self):
        """Decrypting an empty API key should raise ValueError."""
        from crypto import decrypt_api_key

        with pytest.raises(ValueError):
            decrypt_api_key("")

    # ── rotate_encryption_key ──

    def test_rotate_encryption_key(self):
        """Should re-encrypt a value with a new key."""
        from crypto import rotate_encryption_key

        old_key = Fernet.generate_key()
        new_key = Fernet.generate_key()
        old_fernet = Fernet(old_key)

        original = "sensitive-data"
        encrypted_old = old_fernet.encrypt(original.encode()).decode()

        re_encrypted = rotate_encryption_key(old_key, new_key, encrypted_old)

        # Verify re-encrypted value decrypts with new key
        new_fernet = Fernet(new_key)
        assert new_fernet.decrypt(re_encrypted.encode()).decode() == original

        # Old key should NOT decrypt the new token
        with pytest.raises((Exception,)):  # noqa: B017
            old_fernet.decrypt(re_encrypted.encode())

    # ── get_fernet with env var ──

    def test_get_fernet_uses_env_var(self):
        """Should use FERNET_KEY env var when set."""
        from crypto import get_fernet

        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"FERNET_KEY": key}):
            f = get_fernet()
            # Should be able to encrypt/decrypt
            token = f.encrypt(b"test")
            assert f.decrypt(token) == b"test"
