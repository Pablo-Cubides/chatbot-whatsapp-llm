"""
API Manager - Sistema seguro de gestión de claves de API
Maneja el almacenamiento encriptado de claves de API para servicios externos
"""

import os
import json
import base64
from datetime import datetime
from cryptography.fernet import Fernet
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class APIManager:
    """Gestor seguro de claves de API"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.apis_file = os.path.join(data_dir, 'encrypted_apis.json')
        self.key_file = os.path.join(data_dir, 'api_encryption.key')
        self.fernet = self._init_encryption()
        
        # Configuración de proveedores de API
        self.api_providers = {
            'openai': {
                'name': 'OpenAI',
                'description': 'GPT-4, GPT-3.5-turbo y otros modelos de OpenAI',
                'base_url': 'https://api.openai.com/v1',
                'key_format': 'sk-...',
                'test_endpoint': '/models',
                'pricing_info': {
                    'gpt-4': 0.03,  # USD per 1K tokens (input)
                    'gpt-3.5-turbo': 0.0015
                }
            },
            'anthropic': {
                'name': 'Claude (Anthropic)',
                'description': 'Claude-3, Claude-2 y otros modelos de Anthropic',
                'base_url': 'https://api.anthropic.com',
                'key_format': 'sk-ant-...',
                'test_endpoint': '/v1/messages',
                'pricing_info': {
                    'claude-3-opus': 0.015,
                    'claude-3-sonnet': 0.003
                }
            },
            'google': {
                'name': 'Gemini (Google)',
                'description': 'Gemini Pro, Gemini Ultra y otros modelos de Google',
                'base_url': 'https://generativelanguage.googleapis.com/v1beta',
                'key_format': 'AIza...',
                'test_endpoint': '/models',
                'pricing_info': {
                    'gemini-pro': 0.0005,
                    'gemini-ultra': 0.001
                }
            },
            'xai': {
                'name': 'X.AI (Grok)',
                'description': 'Grok y otros modelos de X.AI',
                'base_url': 'https://api.x.ai/v1',
                'key_format': 'xai-...',
                'test_endpoint': '/models',
                'pricing_info': {
                    'grok-beta': 0.002
                }
            }
        }
    
    def _init_encryption(self) -> Fernet:
        """Inicializar sistema de encriptación"""
        try:
            if os.path.exists(self.key_file):
                # Cargar clave existente
                with open(self.key_file, 'rb') as f:
                    key = f.read()
            else:
                # Generar nueva clave
                key = Fernet.generate_key()
                os.makedirs(self.data_dir, exist_ok=True)
                with open(self.key_file, 'wb') as f:
                    f.write(key)
                # Proteger el archivo de clave
                if os.name != 'nt':  # Unix/Linux
                    os.chmod(self.key_file, 0o600)
                    
            return Fernet(key)
        except Exception as e:
            logger.error(f"Error initializing encryption: {e}")
            raise
    
    def _load_encrypted_data(self) -> Dict:
        """Cargar datos encriptados"""
        if not os.path.exists(self.apis_file):
            return {}
        
        try:
            with open(self.apis_file, 'r') as f:
                encrypted_data = json.load(f)
            return encrypted_data
        except Exception as e:
            logger.error(f"Error loading encrypted APIs: {e}")
            return {}
    
    def _save_encrypted_data(self, data: Dict) -> bool:
        """Guardar datos encriptados"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.apis_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving encrypted APIs: {e}")
            return False
    
    def _encrypt_api_key(self, api_key: str) -> str:
        """Encriptar clave de API"""
        try:
            encrypted_key = self.fernet.encrypt(api_key.encode())
            return base64.b64encode(encrypted_key).decode()
        except Exception as e:
            logger.error(f"Error encrypting API key: {e}")
            raise
    
    def _decrypt_api_key(self, encrypted_key: str) -> str:
        """Desencriptar clave de API"""
        try:
            encrypted_bytes = base64.b64decode(encrypted_key.encode())
            decrypted_key = self.fernet.decrypt(encrypted_bytes)
            return decrypted_key.decode()
        except Exception as e:
            logger.error(f"Error decrypting API key: {e}")
            raise
    
    def store_api_key(self, provider: str, api_key: str, metadata: Optional[Dict] = None) -> bool:
        """
        Almacenar clave de API de forma segura
        
        Args:
            provider: Proveedor de API (openai, anthropic, google, xai)
            api_key: Clave de API a almacenar
            metadata: Metadatos adicionales (opcional)
        """
        if provider not in self.api_providers:
            raise ValueError(f"Proveedor no soportado: {provider}")
        
        try:
            # Encriptar la clave
            encrypted_key = self._encrypt_api_key(api_key)
            
            # Cargar datos existentes
            data = self._load_encrypted_data()
            
            # Almacenar datos del proveedor
            data[provider] = {
                'encrypted_key': encrypted_key,
                'provider_info': self.api_providers[provider],
                'metadata': metadata or {},
                'created_at': datetime.now().isoformat(),
                'is_active': True
            }
            
            # Guardar datos
            return self._save_encrypted_data(data)
            
        except Exception as e:
            logger.error(f"Error storing API key for {provider}: {e}")
            return False
    
    def get_api_key(self, provider: str, decrypt: bool = True) -> Optional[str]:
        """
        Obtener clave de API
        
        Args:
            provider: Proveedor de API
            decrypt: Si desencriptar la clave (True) o devolver encriptada (False)
        """
        try:
            data = self._load_encrypted_data()
            
            if provider not in data:
                return None
            
            encrypted_key = data[provider]['encrypted_key']
            
            if decrypt:
                return self._decrypt_api_key(encrypted_key)
            else:
                # Devolver parcialmente oculta para UI
                if len(encrypted_key) > 8:
                    return encrypted_key[:4] + '...' + encrypted_key[-4:]
                return '***'
                
        except Exception as e:
            logger.error(f"Error getting API key for {provider}: {e}")
            return None
    
    def list_configured_apis(self) -> Dict:
        """Listar APIs configuradas con información segura"""
        try:
            data = self._load_encrypted_data()
            result = {}
            
            for provider, info in data.items():
                if provider in self.api_providers:
                    result[provider] = {
                        'name': self.api_providers[provider]['name'],
                        'description': self.api_providers[provider]['description'],
                        'is_active': info.get('is_active', True),
                        'has_key': True,
                        'key_preview': self.get_api_key(provider, decrypt=False),
                        'metadata': info.get('metadata', {}),
                        'pricing_info': self.api_providers[provider].get('pricing_info', {})
                    }
            
            # Agregar proveedores no configurados
            for provider, provider_info in self.api_providers.items():
                if provider not in result:
                    result[provider] = {
                        'name': provider_info['name'],
                        'description': provider_info['description'],
                        'is_active': False,
                        'has_key': False,
                        'key_preview': None,
                        'metadata': {},
                        'pricing_info': provider_info.get('pricing_info', {})
                    }
            
            return result
            
        except Exception as e:
            logger.error(f"Error listing APIs: {e}")
            return {}
    
    def remove_api_key(self, provider: str) -> bool:
        """Eliminar clave de API"""
        try:
            data = self._load_encrypted_data()
            
            if provider in data:
                del data[provider]
                return self._save_encrypted_data(data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing API key for {provider}: {e}")
            return False
    
    def test_api_connection(self, provider: str) -> Dict:
        """Probar conexión con API"""
        try:
            api_key = self.get_api_key(provider)
            if not api_key:
                return {
                    'success': False,
                    'error': 'No API key configured'
                }
            
            provider_info = self.api_providers.get(provider)
            if not provider_info:
                return {
                    'success': False,
                    'error': 'Unsupported provider'
                }
            
            # Aquí iría la lógica específica de test para cada proveedor
            # Por ahora retornamos éxito si tenemos la clave
            return {
                'success': True,
                'message': f'API key configured for {provider_info["name"]}',
                'provider': provider_info['name']
            }
            
        except Exception as e:
            logger.error(f"Error testing API connection for {provider}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_provider_info(self, provider: str) -> Optional[Dict]:
        """Obtener información del proveedor"""
        return self.api_providers.get(provider)
    
    def update_api_metadata(self, provider: str, metadata: Dict) -> bool:
        """Actualizar metadatos de API"""
        try:
            data = self._load_encrypted_data()
            
            if provider in data:
                data[provider]['metadata'].update(metadata)
                return self._save_encrypted_data(data)
            
            return False
            
        except Exception as e:
            logger.error(f"Error updating metadata for {provider}: {e}")
            return False