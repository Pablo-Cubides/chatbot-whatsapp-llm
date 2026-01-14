"""
Tests para el sistema de autenticación
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from services.auth_system import AuthManager, get_current_user, require_admin


class TestAuthManager:
    
    def setup_method(self):
        """Setup para cada test"""
        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'JWT_SECRET': 'test-secret-key-for-testing-minimum-32-chars',
            'ADMIN_USERNAME': 'test_admin',
            'ADMIN_PASSWORD': 'test_password_123',
            'OPERATOR_USERNAME': 'test_operator',
            'OPERATOR_PASSWORD': 'test_op_pass_456'
        })
        self.env_patcher.start()
        
        self.auth_manager = AuthManager()
    
    def teardown_method(self):
        """Cleanup después de cada test"""
        self.env_patcher.stop()
    
    def test_hash_password(self):
        """Test que el hash de password es seguro"""
        password = "test_password_123"
        hashed = self.auth_manager._hash_password(password)
        
        # Verificar que el hash es diferente del password original
        assert hashed != password
        # Verificar que es un string de bcrypt válido
        assert hashed.startswith('$2b$')
        assert len(hashed) == 60  # bcrypt hash length
    
    def test_verify_password_correct(self):
        """Test verificación de password correcto"""
        password = "test_password_123"
        hashed = self.auth_manager._hash_password(password)
        
        assert self.auth_manager._verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test verificación de password incorrecto"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = self.auth_manager._hash_password(password)
        
        assert self.auth_manager._verify_password(wrong_password, hashed) is False
    
    def test_authenticate_user_success(self):
        """Test autenticación exitosa"""
        result = self.auth_manager.authenticate_user('test_admin', 'test_password_123')
        
        assert result is not None
        assert result['username'] == 'test_admin'
        assert result['role'] == 'admin'
        assert 'permissions' in result
        assert 'login_time' in result
    
    def test_authenticate_user_wrong_password(self):
        """Test autenticación con password incorrecto"""
        result = self.auth_manager.authenticate_user('test_admin', 'wrong_password')
        
        assert result is None
    
    def test_authenticate_user_nonexistent(self):
        """Test autenticación con usuario inexistente"""
        result = self.auth_manager.authenticate_user('nonexistent_user', 'any_password')
        
        assert result is None
    
    def test_create_access_token(self):
        """Test creación de token JWT"""
        user_data = {
            'username': 'test_user',
            'role': 'admin',
            'permissions': ['all']
        }
        
        token = self.auth_manager.create_access_token(user_data)
        
        assert isinstance(token, str)
        assert len(token) > 100  # JWT tokens son largos
        assert '.' in token  # JWT format has dots
    
    def test_verify_token_valid(self):
        """Test verificación de token válido"""
        user_data = {
            'username': 'test_admin',
            'role': 'admin',
            'permissions': ['all']
        }
        
        token = self.auth_manager.create_access_token(user_data)
        result = self.auth_manager.verify_token(token)
        
        assert result is not None
        assert result['sub'] == 'test_admin'
        assert 'exp' in result
        assert 'iat' in result
    
    def test_verify_token_invalid(self):
        """Test verificación de token inválido"""
        invalid_token = "invalid.jwt.token"
        result = self.auth_manager.verify_token(invalid_token)
        
        assert result is None
    
    def test_change_password_success(self):
        """Test cambio de password exitoso"""
        username = 'test_admin'
        current_password = 'test_password_123'
        new_password = 'new_secure_password_456'
        
        result = self.auth_manager.change_password(username, current_password, new_password)
        
        assert result is True
        # Verificar que el nuevo password funciona
        auth_result = self.auth_manager.authenticate_user(username, new_password)
        assert auth_result is not None
    
    def test_change_password_wrong_current(self):
        """Test cambio de password con password actual incorrecto"""
        username = 'test_admin'
        wrong_current_password = 'wrong_password'
        new_password = 'new_secure_password_456'
        
        result = self.auth_manager.change_password(username, wrong_current_password, new_password)
        
        assert result is False
    
    def test_change_password_too_short(self):
        """Test cambio de password con password nuevo muy corto"""
        username = 'test_admin'
        current_password = 'test_password_123'
        new_password = '123'  # Muy corto
        
        result = self.auth_manager.change_password(username, current_password, new_password)
        
        assert result is False
    
    @patch.dict(os.environ, {}, clear=True)
    def test_jwt_secret_missing_raises_error(self):
        """Test que falla si no hay JWT_SECRET"""
        with pytest.raises(ValueError, match="JWT_SECRET no está configurado"):
            AuthManager()
    
    def test_jwt_secret_too_short_warning(self, caplog):
        """Test warning si JWT_SECRET es muy corto"""
        with patch.dict(os.environ, {
            'JWT_SECRET': 'short',
            'ADMIN_USERNAME': 'admin',
            'ADMIN_PASSWORD': 'password123'
        }):
            AuthManager()
            assert "JWT_SECRET es muy corto" in caplog.text


class TestAuthDependencies:
    """Tests para las dependencias de FastAPI"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.env_patcher = patch.dict(os.environ, {
            'JWT_SECRET': 'test-secret-key-for-testing-minimum-32-chars',
            'ADMIN_USERNAME': 'test_admin',
            'ADMIN_PASSWORD': 'test_password_123'
        })
        self.env_patcher.start()
        
    def teardown_method(self):
        """Cleanup después de cada test"""
        self.env_patcher.stop()
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_credentials(self):
        """Test get_current_user sin credenciales"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)
        
        assert exc_info.value.status_code == 401
        assert "Token de autorización requerido" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_require_admin_non_admin(self):
        """Test require_admin con usuario no admin"""
        non_admin_user = {
            'username': 'operator',
            'role': 'operator',
            'permissions': ['view']
        }
    
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(non_admin_user)
    
        assert exc_info.value.status_code == 403
        assert "administrador" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_require_admin_success(self):
        """Test require_admin con usuario admin"""
        admin_user = {
            'username': 'admin',
            'role': 'admin',
            'permissions': ['all']
        }
        
        result = await require_admin(admin_user)
        assert result == admin_user


if __name__ == "__main__":
    pytest.main([__file__])
