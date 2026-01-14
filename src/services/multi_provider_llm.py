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
    GROK = "grok"  # Alias para xAI

@dataclass
class APIConfig:
    name: str
    api_key: Optional[str]
    base_url: str
    model: str
    active: bool = True
    max_tokens: int = 2000
    temperature: float = 0.7
    is_reasoning: bool = False  # Para distinguir modelos de razonamiento
    is_free: bool = False       # Para identificar modelos gratuitos
    
class MultiProviderLLM:
    def __init__(self):
        self.providers = {}
        self.fallback_order = []
        self.load_configurations()
    
    def load_configurations(self):
        """Carga configuraciones de todos los proveedores desde .env"""
        
        # Gemini (Excelente relación calidad/precio, bueno para uso general)
        if os.getenv('GEMINI_API_KEY'):
            self.providers[LLMProvider.GEMINI] = APIConfig(
                name="Google Gemini",
                api_key=os.getenv('GEMINI_API_KEY'),
                base_url="https://generativelanguage.googleapis.com/v1beta",
                model=os.getenv('GEMINI_MODEL', 'gemini-1.5-flash'),
                is_reasoning=False,
                is_free=True  # 15 RPM gratuitas
            )
        
        # xAI Grok (Excelente para razonamiento y análisis crítico)
        if os.getenv('XAI_API_KEY'):
            self.providers[LLMProvider.XAI] = APIConfig(
                name="xAI Grok",
                api_key=os.getenv('XAI_API_KEY'),
                base_url=os.getenv('XAI_BASE_URL', 'https://api.x.ai/v1'),
                model=os.getenv('XAI_MODEL', 'grok-beta'),
                is_reasoning=True,  # Excelente para razonamiento
                is_free=True  # Límites generosos en beta
            )
        
        # OpenAI (Mejor calidad general, pero más caro)
        if os.getenv('OPENAI_API_KEY'):
            self.providers[LLMProvider.OPENAI] = APIConfig(
                name="OpenAI",
                api_key=os.getenv('OPENAI_API_KEY'),
                base_url=os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1'),
                model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
                is_reasoning=True,  # GPT-4 es bueno para razonamiento
                is_free=False  # Pago después del crédito inicial
            )
        
        # Claude (Excelente para análisis profundo)
        if os.getenv('CLAUDE_API_KEY'):
            self.providers[LLMProvider.CLAUDE] = APIConfig(
                name="Anthropic Claude",
                api_key=os.getenv('CLAUDE_API_KEY'),
                base_url="https://api.anthropic.com",
                model=os.getenv('CLAUDE_MODEL', 'claude-3-haiku-20240307'),
                is_reasoning=True,
                is_free=False
            )
        
        # Ollama (Local, completamente gratuito)
        if self._check_ollama_available():
            self.providers[LLMProvider.OLLAMA] = APIConfig(
                name="Ollama (Local)",
                api_key=None,
                base_url=os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
                model=os.getenv('OLLAMA_MODEL', 'llama3.2:3b'),
                is_reasoning=False,  # Modelos pequeños, menos razonamiento
                is_free=True  # Completamente gratuito
            )
        
        # LM Studio (Local, completamente gratuito)
        if self._check_lmstudio_available():
            self.providers[LLMProvider.LM_STUDIO] = APIConfig(
                name="LM Studio (Local)",
                api_key=None,
                base_url=os.getenv('LM_STUDIO_URL', 'http://127.0.0.1:1234/v1'),
                model=os.getenv('LM_STUDIO_MODEL', 'nemotron-mini-4b-instruct'),
                is_reasoning=False,
                is_free=True  # Completamente gratuito
            )
        
        # Configurar orden de fallback inteligente
        self._setup_intelligent_fallback()
        
        logger.info(f"Configurados {len(self.providers)} proveedores de IA")
        self._log_provider_capabilities()
    
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
    
    def _setup_intelligent_fallback(self):
        """Configura orden de fallback inteligente basado en benchmarks y uso"""
        
        # Para conversaciones normales: Priorizar calidad/precio y velocidad
        self.normal_fallback = []
        self.reasoning_fallback = []
        self.free_only_fallback = []
        
        # Orden personalizado desde .env o por defecto basado en benchmarks
        fallback_order_env = os.getenv('AI_FALLBACK_ORDER', 'gemini,xai,openai,claude,ollama,lmstudio').split(',')
        
        # Clasificar proveedores por tipo
        for provider_name in fallback_order_env:
            try:
                if provider_name == 'grok':
                    provider_name = 'xai'  # Alias
                
                provider = LLMProvider(provider_name)
                if provider not in self.providers or not self.providers[provider].active:
                    continue
                
                config = self.providers[provider]
                
                # Para conversaciones normales
                self.normal_fallback.append(provider)
                
                # Para razonamiento (solo modelos buenos en razonamiento)
                if config.is_reasoning:
                    self.reasoning_fallback.append(provider)
                
                # Para modo gratuito únicamente
                if config.is_free:
                    self.free_only_fallback.append(provider)
                    
            except ValueError:
                logger.warning(f"Proveedor desconocido en fallback order: {provider_name}")
                continue
        
        # Si no hay modelos de razonamiento, usar los normales
        if not self.reasoning_fallback:
            self.reasoning_fallback = self.normal_fallback.copy()
        
        # Asegurar que siempre haya fallback gratuito
        if not self.free_only_fallback:
            self.free_only_fallback = [p for p in self.normal_fallback if self.providers[p].is_free]
        
        logger.info(f"Fallback normal: {[p.value for p in self.normal_fallback]}")
        logger.info(f"Fallback razonamiento: {[p.value for p in self.reasoning_fallback]}")
        logger.info(f"Fallback gratuito: {[p.value for p in self.free_only_fallback]}")
    
    def _log_provider_capabilities(self):
        """Log de capacidades de cada proveedor"""
        for provider, config in self.providers.items():
            capabilities = []
            if config.is_reasoning:
                capabilities.append("🧠 Razonamiento")
            if config.is_free:
                capabilities.append("🆓 Gratuito")
            if not config.api_key:
                capabilities.append("📍 Local")
            
            logger.info(f"✅ {config.name}: {', '.join(capabilities) if capabilities else 'Estándar'}")
    
    def get_fallback_order(self, use_case: str = "normal", free_only: bool = False) -> List[LLMProvider]:
        """Retorna el orden de fallback según el caso de uso"""
        
        if free_only or os.getenv('ENABLE_FREE_MODELS_FALLBACK', 'false').lower() == 'true':
            return self.free_only_fallback
        elif use_case == "reasoning":
            return self.reasoning_fallback
        else:
            return self.normal_fallback
    
    async def generate_response(self, 
                              messages: List[Dict[str, str]], 
                              business_context: Optional[Dict] = None,
                              use_case: str = "normal",
                              free_only: bool = False,
                              max_retries: int = 3) -> Dict[str, Any]:
        """Genera respuesta usando el proveedor disponible con fallback automático"""
        
        # Determinar si el admin habilitó solo modelos gratuitos
        admin_free_only = os.getenv('ENABLE_FREE_MODELS_FALLBACK', 'false').lower() == 'true'
        if admin_free_only:
            free_only = True
        
        fallback_providers = self.get_fallback_order(use_case, free_only)
        
        logger.info(f"Usando caso: {use_case}, solo gratuitos: {free_only}")
        
        for provider in fallback_providers:
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
                        'tokens_used': result.get('tokens_used', 0),
                        'is_free': self.providers[provider].is_free,
                        'use_case': use_case
                    }
                
            except Exception as e:
                logger.warning(f"❌ Error con {provider.value}: {str(e)}")
                continue
        
        # Si todos los proveedores fallan
        return {
            'success': False,
            'error': f'Todos los proveedores para {use_case} no están disponibles',
            'response': self._get_fallback_response(business_context),
            'provider': 'fallback',
            'use_case': use_case
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
        """Llama a Claude API con formato correcto de Anthropic"""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-Api-Key": config.api_key,
                "anthropic-version": "2023-06-01"
            }
            
            # Convertir mensajes al formato de Claude
            claude_messages = []
            system_message = ""
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message += msg["content"] + "\n"
                else:
                    claude_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            payload = {
                "model": config.model,
                "messages": claude_messages,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature
            }
            
            if system_message.strip():
                payload["system"] = system_message.strip()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.base_url}/v1/messages",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('content', [])
                        if content and len(content) > 0:
                            text = content[0].get('text', '')
                            return {
                                'success': True,
                                'response': text,
                                'tokens_used': data.get('usage', {}).get('input_tokens', 0) + 
                                             data.get('usage', {}).get('output_tokens', 0)
                            }
                    
                    error_text = await response.text()
                    return {'success': False, 'error': f"Claude API Error: {error_text}"}
        
        except Exception as e:
            return {'success': False, 'error': f"Claude Exception: {str(e)}"}
    
    async def _call_xai(self, config: APIConfig, messages: List[Dict]) -> Dict:
        """Llama a xAI Grok API"""
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
                    return {'success': False, 'error': f"xAI Error: {error_text}"}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
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
                'local': provider in [LLMProvider.OLLAMA, LLMProvider.LM_STUDIO],
                'is_free': config.is_free,
                'is_reasoning': config.is_reasoning,
                'capabilities': self._get_provider_capabilities(config)
            }
            for provider, config in self.providers.items()
        ]
    
    def _get_provider_capabilities(self, config: APIConfig) -> List[str]:
        """Retorna lista de capacidades del proveedor"""
        capabilities = []
        if config.is_reasoning:
            capabilities.append("Razonamiento")
        if config.is_free:
            capabilities.append("Gratuito")
        if not config.api_key:
            capabilities.append("Local")
        return capabilities
    
    def get_providers_by_type(self, reasoning: bool = False, free_only: bool = False) -> List[Dict[str, Any]]:
        """Retorna proveedores filtrados por tipo"""
        all_providers = self.get_available_providers()
        
        filtered = []
        for provider in all_providers:
            if reasoning and not provider['is_reasoning']:
                continue
            if free_only and not provider['is_free']:
                continue
            filtered.append(provider)
        
        return filtered

# Instancia global
llm_manager = MultiProviderLLM()
