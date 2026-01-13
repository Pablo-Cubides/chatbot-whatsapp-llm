"""
🤖 Gestor de APIs Multi-Proveedor para Chatbot Universal
Maneja múltiples proveedores de IA con fallback automático
"""

import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class LLMProvider(Enum):
    GEMINI = "gemini"
    OPENAI = "openai"
    CLAUDE = "claude"
    OLLAMA = "ollama"
    LM_STUDIO = "lmstudio"
    XAI = "xai"

@dataclass
class APIConfig:
    name: str
    api_key: Optional[str]
    base_url: str
    model: str
    active: bool = True
    max_tokens: int = 2000
    temperature: float = 0.7
    
class MultiProviderLLM:
    def __init__(self):
        self.providers = {}
        self.fallback_order = []
        self.load_configurations()
    
    def load_configurations(self):
        """Carga configuraciones de todos los proveedores desde .env"""
        
        # Gemini
        if os.getenv('GEMINI_API_KEY'):
            self.providers[LLMProvider.GEMINI] = APIConfig(
                name="Google Gemini",
                api_key=os.getenv('GEMINI_API_KEY'),
                base_url="https://generativelanguage.googleapis.com/v1beta",
                model=os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
            )
        
        # OpenAI
        if os.getenv('OPENAI_API_KEY'):
            self.providers[LLMProvider.OPENAI] = APIConfig(
                name="OpenAI",
                api_key=os.getenv('OPENAI_API_KEY'),
                base_url=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
            )
        
        # Claude
        if os.getenv('CLAUDE_API_KEY'):
            self.providers[LLMProvider.CLAUDE] = APIConfig(
                name="Anthropic Claude",
                api_key=os.getenv('CLAUDE_API_KEY'),
                base_url="https://api.anthropic.com",
                model=os.getenv('CLAUDE_MODEL', 'claude-3-haiku-20240307')
            )
        
        # Ollama (Local)
        if self._check_ollama_available():
            self.providers[LLMProvider.OLLAMA] = APIConfig(
                name="Ollama (Local)",
                api_key=None,
                base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
                model=os.getenv('OLLAMA_MODEL', 'llama3.2:3b')
            )
        
        # LM Studio (Local)
        if self._check_lmstudio_available():
            self.providers[LLMProvider.LM_STUDIO] = APIConfig(
                name="LM Studio (Local)",
                api_key=None,
                base_url=os.getenv('LM_STUDIO_URL', 'http://127.0.0.1:1234/v1'),
                model=os.getenv('LM_STUDIO_MODEL', 'nemotron-mini-4b-instruct')
            )
        
        # xAI Grok
        if os.getenv('XAI_API_KEY'):
            self.providers[LLMProvider.XAI] = APIConfig(
                name="xAI Grok",
                api_key=os.getenv('XAI_API_KEY'),
                base_url="https://api.x.ai/v1",
                model=os.getenv('XAI_MODEL', 'grok-beta')
            )
        
        # Configurar orden de fallback
        default_provider = os.getenv('DEFAULT_LLM_PROVIDER', 'gemini')
        self._setup_fallback_order(default_provider)
        
        logger.info(f"Configurados {len(self.providers)} proveedores de IA")
    
    def _check_ollama_available(self) -> bool:
        """Verifica si Ollama está disponible"""
        try:
            import requests
            response = requests.get(f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/version", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _check_lmstudio_available(self) -> bool:
        """Verifica si LM Studio está disponible"""
        try:
            import requests
            response = requests.get(f"{os.getenv('LM_STUDIO_URL', 'http://127.0.0.1:1234')}/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def _setup_fallback_order(self, default_provider: str):
        """Configura el orden de fallback de proveedores"""
        # Prioridad: Default -> Locales (gratis) -> Comerciales (pagos)
        priority_order = [
            default_provider,
            'ollama',      # Local gratuito
            'lmstudio',    # Local gratuito  
            'gemini',      # Freemium generoso
            'openai',      # Económico
            'claude',      # Más caro
            'xai'          # Beta
        ]
        
        self.fallback_order = []
        for provider_name in priority_order:
            try:
                provider = LLMProvider(provider_name)
                if provider in self.providers and self.providers[provider].active:
                    self.fallback_order.append(provider)
            except ValueError:
                continue
        
        logger.info(f"Orden de fallback: {[p.value for p in self.fallback_order]}")
    
    async def generate_response(self, 
                              messages: List[Dict[str, str]], 
                              business_context: Optional[Dict] = None,
                              max_retries: int = 3) -> Dict[str, Any]:
        """Genera respuesta usando el proveedor disponible con fallback automático"""
        
        for provider in self.fallback_order:
            try:
                logger.info(f"Intentando con proveedor: {provider.value}")
                result = await self._call_provider(provider, messages, business_context)
                
                if result and result.get('success'):
                    logger.info(f"✅ Respuesta exitosa de {provider.value}")
                    return {
                        'success': True,
                        'response': result['response'],
                        'provider': provider.value,
                        'model': self.providers[provider].model,
                        'tokens_used': result.get('tokens_used', 0)
                    }
                
            except Exception as e:
                logger.warning(f"❌ Error con {provider.value}: {str(e)}")
                continue
        
        # Si todos los proveedores fallan
        return {
            'success': False,
            'error': 'Todos los proveedores de IA no están disponibles',
            'response': self._get_fallback_response(business_context),
            'provider': 'fallback'
        }
    
    async def _call_provider(self, 
                           provider: LLMProvider, 
                           messages: List[Dict[str, str]], 
                           business_context: Optional[Dict] = None) -> Dict[str, Any]:
        """Llama a un proveedor específico"""
        
        config = self.providers[provider]
        
        if provider == LLMProvider.GEMINI:
            return await self._call_gemini(config, messages, business_context)
        elif provider == LLMProvider.OPENAI:
            return await self._call_openai(config, messages)
        elif provider == LLMProvider.CLAUDE:
            return await self._call_claude(config, messages)
        elif provider == LLMProvider.OLLAMA:
            return await self._call_ollama(config, messages)
        elif provider == LLMProvider.LM_STUDIO:
            return await self._call_lmstudio(config, messages)
        elif provider == LLMProvider.XAI:
            return await self._call_xai(config, messages)
        
        return {'success': False, 'error': 'Proveedor no soportado'}
    
    async def _call_gemini(self, config: APIConfig, messages: List[Dict], context: Optional[Dict] = None) -> Dict:
        """Llama a Google Gemini API"""
        try:
            # Convertir mensajes al formato de Gemini
            contents = []
            for msg in messages:
                contents.append({
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [{"text": msg["content"]}]
                })
            
            url = f"{config.base_url}/models/{config.model}:generateContent"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": config.temperature,
                    "maxOutputTokens": config.max_tokens
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{url}?key={config.api_key}",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'candidates' in data and len(data['candidates']) > 0:
                            text = data['candidates'][0]['content']['parts'][0]['text']
                            return {
                                'success': True,
                                'response': text,
                                'tokens_used': data.get('usageMetadata', {}).get('totalTokenCount', 0)
                            }
                    
                    error_text = await response.text()
                    return {'success': False, 'error': f"API Error: {error_text}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _call_openai(self, config: APIConfig, messages: List[Dict]) -> Dict:
        """Llama a OpenAI API"""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}"
            }
            
            payload = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'response': data['choices'][0]['message']['content'],
                            'tokens_used': data.get('usage', {}).get('total_tokens', 0)
                        }
                    
                    error_text = await response.text()
                    return {'success': False, 'error': f"API Error: {error_text}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _call_ollama(self, config: APIConfig, messages: List[Dict]) -> Dict:
        """Llama a Ollama local"""
        try:
            payload = {
                "model": config.model,
                "messages": messages,
                "stream": False
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.base_url}/api/chat",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'response': data['message']['content'],
                            'tokens_used': 0  # Ollama es local, no cuenta tokens
                        }
                    
                    error_text = await response.text()
                    return {'success': False, 'error': f"Ollama Error: {error_text}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _call_lmstudio(self, config: APIConfig, messages: List[Dict]) -> Dict:
        """Llama a LM Studio local"""
        try:
            payload = {
                "model": config.model,
                "messages": messages,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.base_url}/chat/completions",
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'response': data['choices'][0]['message']['content'],
                            'tokens_used': 0  # LM Studio es local
                        }
                    
                    error_text = await response.text()
                    return {'success': False, 'error': f"LM Studio Error: {error_text}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def _call_claude(self, config: APIConfig, messages: List[Dict]) -> Dict:
        """Llama a Claude API"""
        # Implementación similar a OpenAI pero con formato de Claude
        return {'success': False, 'error': 'Claude no implementado aún'}
    
    async def _call_xai(self, config: APIConfig, messages: List[Dict]) -> Dict:
        """Llama a xAI Grok API"""
        # Implementación similar a OpenAI
        return {'success': False, 'error': 'xAI no implementado aún'}
    
    def _get_fallback_response(self, context: Optional[Dict] = None) -> str:
        """Respuesta de emergencia cuando todos los proveedores fallan"""
        business_name = context.get('business_name', 'nuestro negocio') if context else 'nuestro negocio'
        
        return (
            f"Disculpa, estoy experimentando dificultades técnicas temporales. "
            f"Por favor, contacta directamente con {business_name} o intenta nuevamente en unos minutos. "
            f"Apreciamos tu paciencia. 🙏"
        )
    
    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Retorna lista de proveedores disponibles con su estado"""
        return [
            {
                'name': config.name,
                'provider': provider.value,
                'model': config.model,
                'active': config.active,
                'local': provider in [LLMProvider.OLLAMA, LLMProvider.LM_STUDIO]
            }
            for provider, config in self.providers.items()
        ]

# Instancia global
llm_manager = MultiProviderLLM()
